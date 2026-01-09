import { Settings, FileText, Code2, CheckCircle2 } from "lucide-react";
import { useInView } from "@/hooks/use-in-view";

interface Step {
  number: number;
  icon: React.ElementType;
  command: string;
  title: string;
  description: string;
}

const steps: Step[] = [
  {
    number: 1,
    icon: FileText,
    command: "/spec",
    title: "Plan",
    description: "Explores codebase, asks questions, generates detailed spec for your approval.",
  },
  {
    number: 2,
    icon: Settings,
    command: "/spec",
    title: "Approve",
    description: "You review, edit if needed, and approve the plan before implementation.",
  },
  {
    number: 3,
    icon: Code2,
    command: "/spec",
    title: "Implement",
    description: "Executes the approved plan with TDD enforcement and quality hooks.",
  },
  {
    number: 4,
    icon: CheckCircle2,
    command: "/spec",
    title: "Verify",
    description: "Runs tests, quality checks, and validates completion based on the plan.",
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

const WorkflowSteps = () => {
  const [headerRef, headerInView] = useInView<HTMLDivElement>();
  const [stepsRef, stepsInView] = useInView<HTMLDivElement>();

  return (
    <section id="workflow" className="py-20 lg:py-28 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto">
        <div
          ref={headerRef}
          className={`animate-on-scroll ${headerInView ? "in-view" : ""}`}
        >
          <SectionHeader
            title="Spec-Driven Development"
            subtitle="A structured workflow that ensures quality at every step"
          />
        </div>
        <div
          ref={stepsRef}
          className={`grid sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8 relative stagger-children ${stepsInView ? "in-view" : ""}`}
        >
          {/* Connecting line (desktop only) */}
          <div className="hidden lg:block absolute top-12 left-[60px] right-[60px] h-0.5 bg-gradient-to-r from-primary via-primary/50 to-primary opacity-30" />

          {steps.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.number} className="relative text-center">
                {/* Step number circle */}
                <div className="relative z-10 w-24 h-24 mx-auto mb-6 rounded-full border-2 border-primary/50 bg-background flex items-center justify-center">
                  <div className="text-center">
                    <Icon className="h-8 w-8 text-primary mx-auto mb-1" />
                    <code className="text-xs text-primary font-mono">{step.command}</code>
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  {step.title}
                </h3>
                <p className="text-muted-foreground text-sm">
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default WorkflowSteps;
