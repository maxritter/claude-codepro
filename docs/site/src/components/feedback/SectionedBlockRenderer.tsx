import { useState, useEffect, useMemo } from "react";
import {
  AlertTriangle,
  BookOpen,
  Bookmark,
  Brain,
  CheckCircle2,
  CheckSquare,
  ChevronDown,
  Circle,
  ClipboardCheck,
  ClipboardList,
  Compass,
  Cpu,
  Crosshair,
  FileCode2,
  FileText,
  HelpCircle,
  History,
  Lightbulb,
  ListTree,
  MonitorCheck,
  MousePointerClick,
  NotebookPen,
  Route,
  Scale,
  SquareX,
  Target,
  Terminal,
  Text as TextIcon,
  Trophy,
  UserRoundCheck,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { BlockRenderer } from "./BlockRenderer";
import { extractObjectiveBlocks, orderSections, stripLabelPrefix } from "./sectioned-block-helpers";
import {
  DISPLAYED_SECTIONS_ORDERED,
  IMPLEMENTATION_TASKS_HEADING,
  SECTIONS_HIDDEN,
  TASKS_HEADING_BUGFIX,
} from "@/lib/sharing/displayed-sections";
import type { Annotation, Block } from "@/lib/annotation/types";

const TASKS_HEADINGS = [IMPLEMENTATION_TASKS_HEADING, TASKS_HEADING_BUGFIX] as const;

/**
 * Section-aware wrapper around BlockRenderer for pilot-shell.com / shared
 * spec viewing.
 *
 * Grouping levels:
 *  - H2 (`##`) → top-level collapsible section.
 *  - Inside `## Implementation Tasks` / `## Tasks`, `### Task N:` H3 → per-task collapsible.
 *  - Inside each task, paragraphs whose content is `**Label:**` → per-field collapsible.
 *
 * Heading blocks are NOT re-rendered inside their own card — the card title
 * already shows the heading. Annotation auto-expand still works by checking
 * the heading block id alongside the body blocks.
 */

interface SectionedBlockRendererProps {
  blocks: Block[];
  annotations: Annotation[];
  selectedAnnotationId: string | null;
  onSelectAnnotation?: (id: string) => void;
  onQuickAnnotate?: (
    blockId: string,
    originalText: string,
    annotationText: string,
  ) => void;
}

interface H2Group {
  heading: string;
  headingBlock: Block;
  blocks: Block[];
}

interface TaskGroup {
  number: number;
  title: string;
  /** null when this group holds prelude blocks that appeared before the first `### Task N:` heading. */
  headingBlock: Block | null;
  blocks: Block[];
}

interface FieldGroup {
  label: string;
  blocks: Block[];
}

// Map section headings to lucide icons (ported from console SpecSection.tsx).
const SECTION_ICONS: Record<string, LucideIcon> = {
  // Spec sections
  Summary: TextIcon,
  Approach: Compass,
  "Fix Approach": Wrench,
  "Feature Inventory": ClipboardList,
  Scope: Target,
  "Out of Scope": SquareX,
  "Autonomous Decisions": Brain,
  "Context for Implementer": BookOpen,
  "Runtime Environment": Terminal,
  Assumptions: Lightbulb,
  "Risks and Mitigations": AlertTriangle,
  "Goal Verification": CheckSquare,
  "E2E Test Scenarios": MonitorCheck,
  "E2E Results": ClipboardCheck,
  "Verification Scenario": MousePointerClick,
  "Open Questions": HelpCircle,
  "Deferred Ideas": Bookmark,
  "Implementation Details": ListTree,
  "Implementation Tasks": ListTree,
  Tasks: ListTree,
  Investigation: HelpCircle,
  "Behavior Contract": Scale,
  // Buildout sections ("Criteria" is the pre-redesign heading)
  "Acceptance Criteria": CheckSquare,
  Criteria: Trophy,
  "Round Log": History,
  // PRD sections
  "Problem Statement": Crosshair,
  "Core User Flows": Route,
  "Technical Context": Cpu,
  "Key Decisions": Scale,
};

// Per-task field icons — matched to the Console SpecTaskCard SubBlock icons.
// Keys are the canonical labels emitted by parsePlanContent's KNOWN_LABEL_FIELDS.
const FIELD_ICONS: Record<string, LucideIcon> = {
  "Definition of Done": CheckSquare,
  DoD: CheckSquare,
  Files: FileCode2,
  "Key Decisions": NotebookPen,
  "Key Decisions / Notes": NotebookPen,
  Notes: NotebookPen,
  "User Action": UserRoundCheck,
};

// Plan-header metadata paragraph: `Created: …\nAuthor: …\nStatus: …\n…`.
// Hidden from the shared view — reviewers don't review progress.
const PLAN_METADATA_RE = /^(Created|Author|Status|Approved|Iterations|Worktree|Type):/m;

function isPlanMetadataBlock(block: Block): boolean {
  return block.type === "paragraph" && PLAN_METADATA_RE.test(block.content);
}

// Top-of-tasks-section progress checklist: `- [x] Task N: …`. Hidden from
// the shared view because each task already renders as its own collapsible.
function isTaskProgressChecklistItem(block: Block): boolean {
  return (
    block.type === "list-item" &&
    typeof block.checked === "boolean" &&
    /^Task\s+\d+:/.test(block.content)
  );
}

// Build a map of task-number → completion state by scanning the section's
// `- [x] Task N: …` prelude checklist. Used to draw the checkbox icon on the
// task card header — same signal the Console SpecTaskCard reads.
function extractTaskCompletion(sectionBlocks: Block[]): Map<number, boolean> {
  const completion = new Map<number, boolean>();
  for (const block of sectionBlocks) {
    if (!isTaskProgressChecklistItem(block)) continue;
    const match = block.content.match(/^Task\s+(\d+):/);
    if (!match) continue;
    completion.set(parseInt(match[1], 10), block.checked === true);
  }
  return completion;
}

function groupByH2(blocks: Block[]): H2Group[] {
  const groups: H2Group[] = [];
  let current: H2Group | null = null;
  for (const block of blocks) {
    if (block.type === "heading" && block.level === 2) {
      if (current) groups.push(current);
      // Heading block is NOT in .blocks — the CollapsibleCard title shows it.
      current = { heading: block.content, headingBlock: block, blocks: [] };
    } else if (current) {
      current.blocks.push(block);
    } else {
      current = { heading: "", headingBlock: block, blocks: [block] };
    }
  }
  if (current) groups.push(current);
  return groups.filter((g) => g.heading || g.blocks.length > 0);
}

function groupByTaskH3(blocks: Block[]): TaskGroup[] {
  const groups: TaskGroup[] = [];
  let current: TaskGroup | null = null;
  const prelude: Block[] = [];
  for (const block of blocks) {
    if (block.type === "heading" && block.level === 3) {
      const m = block.content.match(/^Task\s+(\d+):\s*(.+)$/);
      if (m) {
        if (current) groups.push(current);
        else if (prelude.length > 0) {
          groups.push({ number: 0, title: "", headingBlock: null, blocks: prelude.splice(0) });
        }
        current = {
          number: parseInt(m[1], 10),
          title: m[2].trim(),
          headingBlock: block,
          // Heading block is NOT in .blocks — the CollapsibleCard title shows it.
          blocks: [],
        };
        continue;
      }
    }
    if (current) current.blocks.push(block);
    else prelude.push(block);
  }
  if (current) groups.push(current);
  else if (prelude.length > 0) {
    groups.push({ number: 0, title: "", headingBlock: null, blocks: prelude });
  }
  return groups;
}

function matchLabelMarker(block: Block): string | null {
  if (block.type !== "paragraph") return null;
  const m = block.content.match(/^\*\*([A-Za-z][A-Za-z0-9 /]+):\*\*\s*(.*)$/s);
  if (!m) return null;
  return m[1].trim();
}

function groupByLabel(blocks: Block[]): FieldGroup[] {
  const groups: FieldGroup[] = [];
  let current: FieldGroup | null = null;
  for (const block of blocks) {
    const label = matchLabelMarker(block);
    if (label) {
      if (current) groups.push(current);
      const stripped = stripLabelPrefix(block, label);
      current = { label, blocks: stripped ? [stripped] : [] };
      continue;
    }
    if (current) current.blocks.push(block);
    // No leading-`**Label:**` block → blocks go into the parent task body
    // directly (no synthetic "Notes" group that just mirrors the title).
  }
  if (current) groups.push(current);
  return groups;
}

interface CollapsibleCardProps {
  title: React.ReactNode;
  icon?: LucideIcon;
  defaultOpen: boolean;
  expanded?: boolean;
  rightSlot?: React.ReactNode;
  children: React.ReactNode;
}

function CollapsibleCard({
  title,
  icon: SectionIcon,
  defaultOpen,
  expanded,
  rightSlot,
  children,
}: CollapsibleCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const isOpen = expanded ?? open;
  const setIsOpen = (next: boolean) => setOpen(next);
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center gap-2.5 px-4 py-3 text-left cursor-pointer hover:bg-muted/50 transition-colors"
      >
        {SectionIcon && (
          <SectionIcon size={14} className="text-primary flex-shrink-0" />
        )}
        <div className="flex-1 text-sm font-semibold">{title}</div>
        {rightSlot}
        <ChevronDown
          size={14}
          className={cn(
            "text-muted-foreground/60 transition-transform duration-200",
            isOpen ? "rotate-180" : "",
          )}
        />
      </button>
      {isOpen && (
        <div className="px-4 pb-4 pt-0 border-t border-border/50">
          <div className="pt-3">{children}</div>
        </div>
      )}
    </div>
  );
}

interface FieldRowProps {
  label: string;
  icon: LucideIcon;
  defaultOpen: boolean;
  expanded?: boolean;
  children: React.ReactNode;
}

/**
 * Flat task-field row mirroring the Console SpecTaskCard SubBlock: top border,
 * icon + label + chevron, content drops in below when expanded. Used inside a
 * TaskCard so the fields read as a single attached list, not a stack of
 * nested rounded sub-cards.
 */
function FieldRow({ label, icon: FieldIcon, defaultOpen, expanded, children }: FieldRowProps) {
  const [open, setOpen] = useState(defaultOpen);
  const isOpen = expanded ?? open;
  return (
    <div className="border-t border-border/50">
      <button
        type="button"
        onClick={() => setOpen(!isOpen)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left cursor-pointer hover:bg-muted/50 transition-colors"
      >
        <FieldIcon size={13} className="text-primary/70 flex-shrink-0" />
        <span className="text-xs font-medium flex-1 text-muted-foreground">{label}</span>
        <ChevronDown
          size={12}
          className={cn(
            "text-muted-foreground/40 transition-transform duration-200",
            isOpen ? "rotate-180" : "",
          )}
        />
      </button>
      {isOpen && <div className="px-3 pb-3 pt-1">{children}</div>}
    </div>
  );
}

interface TaskCardProps {
  number: number;
  title: string;
  completed: boolean | null;
  objective: React.ReactNode | null;
  owner: "Agent" | "User";
  expanded: boolean;
  children: React.ReactNode;
}

/**
 * Per-task card matching the Console SpecTaskCard layout:
 *  - Header (always visible): completion icon + "Task N" + title + objective.
 *  - Body (expanded only): flat list of FieldRow entries.
 *
 * The header isn't a `<button>` because the objective renders interactive
 * BlockRenderer content (quick-annotate buttons), which would nest buttons.
 * Instead, the header is a clickable region with role="button" + keyboard
 * handler, and a dedicated chevron button as the accessible toggle target.
 */
function TaskCard({ number, title, completed, objective, owner, expanded, children }: TaskCardProps) {
  const [open, setOpen] = useState(expanded);
  const isOpen = expanded || open;
  const toggle = () => setOpen(!isOpen);
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div
        role="button"
        tabIndex={0}
        aria-expanded={isOpen}
        onClick={toggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            toggle();
          }
        }}
        className="w-full text-left cursor-pointer hover:bg-muted/40 transition-colors"
      >
        <div className="flex items-start gap-2.5 p-3">
          <div className="flex-shrink-0 mt-0.5">
            {completed ? (
              <CheckCircle2 size={16} className="text-green-600 dark:text-green-400" />
            ) : (
              <Circle size={16} className="text-muted-foreground/40" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="text-xs font-mono text-muted-foreground/70">Task {number}</span>
              {owner === "User" && <Badge variant="secondary">User</Badge>}
            </div>
            <div className="text-sm font-semibold mt-0.5 leading-snug">{title}</div>
            {objective && <div className="mt-1.5 text-sm text-muted-foreground">{objective}</div>}
          </div>
          <ChevronDown
            size={14}
            className={cn(
              "text-muted-foreground/40 mt-0.5 flex-shrink-0 transition-transform duration-200",
              isOpen ? "rotate-180" : "",
            )}
          />
        </div>
      </div>
      {isOpen && <>{children}</>}
    </div>
  );
}

export function SectionedBlockRenderer({
  blocks,
  annotations,
  selectedAnnotationId,
  onSelectAnnotation,
  onQuickAnnotate,
}: SectionedBlockRendererProps) {
  const sections = useMemo(
    () => orderSections(groupByH2(blocks), DISPLAYED_SECTIONS_ORDERED, TASKS_HEADINGS, SECTIONS_HIDDEN),
    [blocks],
  );

  const [forceOpenBlockId, setForceOpenBlockId] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedAnnotationId) {
      setForceOpenBlockId(null);
      return;
    }
    const ann = annotations.find((a) => a.id === selectedAnnotationId);
    setForceOpenBlockId(ann?.blockId ?? null);
  }, [selectedAnnotationId, annotations]);

  const renderLeaf = (groupBlocks: Block[]) => (
    <BlockRenderer
      blocks={groupBlocks}
      annotations={annotations}
      selectedAnnotationId={selectedAnnotationId}
      onSelectAnnotation={onSelectAnnotation}
      onQuickAnnotate={onQuickAnnotate}
    />
  );

  const containsBlockOrHeading = (
    groupBlocks: Block[],
    headingBlock: Block | null,
    targetId: string | null,
  ): boolean => {
    if (!targetId) return false;
    if (headingBlock && headingBlock.id === targetId) return true;
    return groupBlocks.some((b) => b.id === targetId);
  };

  return (
    <div className="space-y-2">
      {sections.map((section) => {
        const isTaskSection =
          section.heading === "Implementation Tasks" ||
          section.heading === "Tasks";
        const sectionForceOpen = containsBlockOrHeading(
          section.blocks,
          section.headingBlock,
          forceOpenBlockId,
        );
        if (!section.heading) {
          // Preamble before the first H2: drop the plan-metadata paragraph
          // so reviewers don't see Status/Iterations/Approved/etc.
          const preambleBlocks = section.blocks.filter(
            (b) => !isPlanMetadataBlock(b),
          );
          if (preambleBlocks.length === 0) return null;
          return (
            <div key={`preamble-${section.headingBlock.id}`}>
              {renderLeaf(preambleBlocks)}
            </div>
          );
        }
        const SectionIcon = SECTION_ICONS[section.heading] ?? FileText;
        return (
          <CollapsibleCard
            key={section.headingBlock.id}
            title={section.heading}
            icon={SectionIcon}
            defaultOpen={true}
            expanded={sectionForceOpen || undefined}
          >
            {isTaskSection ? (
              <div className="space-y-2">
                {(() => {
                  const completion = extractTaskCompletion(section.blocks);
                  return groupByTaskH3(section.blocks).map((task) => {
                    const taskForceOpen = containsBlockOrHeading(
                      task.blocks,
                      task.headingBlock,
                      forceOpenBlockId,
                    );
                    // Prelude blocks (before the first `### Task N:`): drop
                    // the progress checklist (`- [x] Task N: …`) — the
                    // per-task cards below already show each task.
                    if (task.headingBlock === null) {
                      const preludeBlocks = task.blocks.filter(
                        (b) => !isTaskProgressChecklistItem(b),
                      );
                      if (preludeBlocks.length === 0) return null;
                      return (
                        <div key={`prelude-${task.blocks[0]?.id ?? "empty"}`}>
                          {renderLeaf(preludeBlocks)}
                        </div>
                      );
                    }
                    const taskHeadingId = task.headingBlock.id;
                    const { objective, rest } = extractObjectiveBlocks(task.blocks);
                    const fields = groupByLabel(rest);
                    const ownerField = fields.find((field) => field.label === "Owner");
                    const owner = ownerField?.blocks.some(
                      (block) => block.type === "paragraph" && block.content.trim() === "User",
                    ) ? "User" : "Agent";
                    const completed = completion.get(task.number) ?? null;
                    return (
                      <TaskCard
                        key={taskHeadingId}
                        number={task.number}
                        title={task.title}
                        completed={completed}
                        objective={
                          objective && objective.length > 0 ? renderLeaf(objective) : null
                        }
                        owner={owner}
                        expanded={taskForceOpen}
                      >
                        {fields.filter((field) => field.label !== "Owner").map((field) => {
                          const fieldForceOpen = containsBlockOrHeading(
                            field.blocks,
                            null,
                            forceOpenBlockId,
                          );
                          const FieldIcon = FIELD_ICONS[field.label] ?? FileText;
                          return (
                            <FieldRow
                              key={`${taskHeadingId}-${field.label}`}
                              label={field.label}
                              icon={FieldIcon}
                              defaultOpen={fieldForceOpen}
                              expanded={fieldForceOpen || undefined}
                            >
                              {renderLeaf(field.blocks)}
                            </FieldRow>
                          );
                        })}
                      </TaskCard>
                    );
                  });
                })()}
              </div>
            ) : (
              renderLeaf(section.blocks)
            )}
          </CollapsibleCard>
        );
      })}
    </div>
  );
}
