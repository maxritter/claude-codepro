import {
  Terminal,
  FileCode2,
  Plug2,
  ShieldCheck,
  Container,
  Infinity as InfinityIcon
} from "lucide-react";
import { useInView } from "@/hooks/use-in-view";

interface InsideItem {
  icon: React.ElementType;
  title: string;
  items: string[];
  highlight?: boolean;
}

const insideItems: InsideItem[] = [
  {
    icon: Terminal,
    title: "Two Development Modes",
    items: [
      "Spec-Driven: /spec for new features with planning",
      "Quick Mode: Just chat for bug fixes and small changes",
      "Both modes get unlimited context via Endless Mode",
      "Choose structured planning or fast iteration",
    ],
  },
  {
    icon: InfinityIcon,
    title: "Endless Mode",
    items: [
      "Removes 200K context limit entirely",
      "Automatic session handoffs when nearing limit",
      "Works in both Spec-Driven and Quick modes",
      "Zero manual intervention required",
    ],
  },
  {
    icon: FileCode2,
    title: "Modular Rules System",
    items: [
      "Auto-loaded from .claude/rules/*.md",
      "Standard rules for TDD, context, best practices",
      "Custom rules in .claude/rules/custom/",
      "Command and standards skills",
    ],
  },
  {
    icon: Plug2,
    title: "Enhanced Context",
    items: [
      "Claude Mem - Cross-session persistent memory",
      "Vexor - Local semantic code search",
      "Context7 - Library documentation lookup",
      "Firecrawl - Web search and scraping"
    ],
  },
  {
    icon: ShieldCheck,
    title: "Quality Hooks",
    items: [
      "Qlty - Post-edit formatting and linting",
      "TDD Enforcer - Pre-edit test requirement",
      "Context Monitor - Warns when context getting full",
      "LSP Servers - Python (Pyright) & TypeScript",
    ],
  },
  {
    icon: Container,
    title: "One-Command Installer",
    items: [
      "Automated Dev Container setup",
      "Optional Python & TypeScript support",
      "Shell integration with ccp alias",
      "Works with VS Code, Cursor, Windsurf",
    ],
  },
];

const SectionHeader = ({ title, subtitle }: { title: string; subtitle?: string }) => (
  <div className="text-center mb-12">
    <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-foreground mb-4">
      {title}
    </h2>
    {subtitle && (
      <p className="text-muted-foreground text-base sm:text-lg max-w-2xl mx-auto">
        {subtitle}
      </p>
    )}
  </div>
);

const WhatsInside = () => {
  const [headerRef, headerInView] = useInView<HTMLDivElement>();
  const [gridRef, gridInView] = useInView<HTMLDivElement>();

  return (
    <section id="features" className="py-20 lg:py-28 px-4 sm:px-6 bg-card/30 relative">
      <div className="max-w-6xl mx-auto">
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
        <div
          ref={headerRef}
          className={`animate-on-scroll ${headerInView ? "in-view" : ""}`}
        >
          <SectionHeader
            title="What's Inside"
            subtitle="Everything you need for professional AI-assisted development"
          />
        </div>

        <div
          ref={gridRef}
          className={`grid md:grid-cols-2 lg:grid-cols-3 gap-6 stagger-children ${gridInView ? "in-view" : ""}`}
        >
          {insideItems.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.title}
                className={`glass rounded-2xl p-6 hover:border-primary/50 transition-all duration-300 ${
                  item.highlight ? "border-red-500/50 bg-red-500/5" : ""
                }`}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">
                    {item.title}
                  </h3>
                </div>
                <ul className="space-y-2">
                  {item.items.map((listItem, i) => (
                    <li key={i} className="text-muted-foreground text-sm flex items-start gap-2">
                      <span className="text-primary mt-1.5 text-xs">•</span>
                      <span>{listItem}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default WhatsInside;
