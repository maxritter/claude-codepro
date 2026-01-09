import { Clock, Zap, AlertTriangle, CheckCircle2, Brain, FileCode2, ShieldCheck } from "lucide-react";
import { useInView } from "@/hooks/use-in-view";

const ComparisonSection = () => {
  const [headerRef, headerInView] = useInView<HTMLDivElement>();
  const [cardsRef, cardsInView] = useInView<HTMLDivElement>();

  return (
    <section className="py-20 lg:py-28 px-4 sm:px-6 relative">
      <div className="max-w-6xl mx-auto">
        {/* Section Header */}
        <div
          ref={headerRef}
          className={`text-center mb-12 animate-on-scroll ${headerInView ? "in-view" : ""}`}
        >
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-foreground mb-4">
            The Difference
          </h2>
          <p className="text-muted-foreground text-base sm:text-lg max-w-2xl mx-auto">
            Same task. Different experience.
          </p>
        </div>

        <div
          ref={cardsRef}
          className={`grid md:grid-cols-2 gap-6 sm:gap-8 stagger-children ${cardsInView ? "in-view" : ""}`}
        >
          {/* Without Claude CodePro */}
          <div className="glass rounded-2xl p-5 sm:p-6 relative border-red-500/20 hover:border-red-500/30 transition-colors">
            <div className="absolute top-3 sm:top-4 right-3 sm:right-4 bg-red-500/20 text-red-400 px-2 sm:px-3 py-1 rounded-full text-xs font-medium">
              Without Structure
            </div>

            {/* Terminal window */}
            <div className="mt-8 space-y-3">
              {/* Terminal header */}
              <div className="bg-background/80 rounded-t-lg px-4 py-2 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/60" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                  <div className="w-3 h-3 rounded-full bg-green-500/60" />
                </div>
                <span className="text-xs text-muted-foreground ml-2 font-mono">terminal</span>
              </div>

              {/* Terminal content */}
              <div className="bg-background/50 rounded-b-lg p-4 font-mono text-xs sm:text-sm space-y-3">
                <div>
                  <span className="text-blue-400">you:</span>
                  <span className="text-muted-foreground ml-2">Add user authentication</span>
                </div>
                <div>
                  <span className="text-primary">claude:</span>
                  <span className="text-muted-foreground ml-2">What framework? What patterns?</span>
                </div>
                <div className="text-red-400/80 flex items-center gap-2 text-xs">
                  <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                  <span>No context from previous sessions</span>
                </div>
                <div className="text-red-400/80 flex items-center gap-2 text-xs">
                  <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                  <span>No codebase knowledge</span>
                </div>
                <div className="border-t border-border/50 pt-3">
                  <span className="text-muted-foreground">...writes code without tests...</span>
                </div>
                <div className="text-red-400/80 flex items-center gap-2 text-xs">
                  <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                  <span>No TDD enforcement</span>
                </div>
                <div className="border-t border-border/50 pt-3">
                  <span className="text-muted-foreground">...commits with issues...</span>
                </div>
                <div className="text-red-400/80 flex items-center gap-2 text-xs">
                  <AlertTriangle className="h-3 w-3 flex-shrink-0" />
                  <span>No quality checks or formatting</span>
                </div>
              </div>
            </div>

            {/* Result */}
            <div className="mt-4 flex items-center justify-center gap-2 text-red-400 text-sm">
              <Clock className="h-4 w-4" />
              <span>Inconsistent. Untested. Risky.</span>
            </div>
          </div>

          {/* With Claude CodePro */}
          <div className="glass rounded-2xl p-5 sm:p-6 relative border-green-500/20 hover:border-green-500/30 transition-colors">
            <div className="absolute top-3 sm:top-4 right-3 sm:right-4 bg-green-500/20 text-green-400 px-2 sm:px-3 py-1 rounded-full text-xs font-medium">
              With Claude CodePro
            </div>

            {/* Terminal window */}
            <div className="mt-8 space-y-3">
              {/* Terminal header */}
              <div className="bg-background/80 rounded-t-lg px-4 py-2 flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/60" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                  <div className="w-3 h-3 rounded-full bg-green-500/60" />
                </div>
                <span className="text-xs text-muted-foreground ml-2 font-mono">ccp</span>
              </div>

              {/* Terminal content */}
              <div className="bg-background/50 rounded-b-lg p-4 font-mono text-xs sm:text-sm space-y-2.5">
                {/* /spec command */}
                <div>
                  <span className="text-primary">/spec</span>
                  <span className="text-muted-foreground ml-2">"Add user authentication"</span>
                </div>
                {/* Context injection */}
                <div className="text-green-400/80 flex items-center gap-2 text-xs">
                  <Brain className="h-3 w-3 flex-shrink-0" />
                  <span>Claude Mem: Context injected</span>
                </div>
                <div className="text-green-400/80 flex items-center gap-2 text-xs">
                  <FileCode2 className="h-3 w-3 flex-shrink-0" />
                  <span>Rules + Skills loaded</span>
                </div>
                <div className="border-t border-border/50 pt-2.5 text-xs">
                  <span className="text-blue-400">→ Planning:</span>
                  <span className="text-muted-foreground ml-1">Exploring codebase...</span>
                </div>
                <div className="text-green-400/80 flex items-center gap-2 text-xs">
                  <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
                  <span>Plan created → Waiting for approval</span>
                </div>
                <div className="border-t border-border/50 pt-2.5 text-xs">
                  <span className="text-blue-400">→ Implementing:</span>
                  <span className="text-muted-foreground ml-1">TDD enforced</span>
                </div>
                <div className="text-green-400/80 flex items-center gap-2 text-xs">
                  <ShieldCheck className="h-3 w-3 flex-shrink-0" />
                  <span>Quality hooks: formatted, linted</span>
                </div>
                <div className="border-t border-border/50 pt-2.5 text-xs">
                  <span className="text-blue-400">→ Verifying:</span>
                  <span className="text-green-400 ml-1">All checks passed ✓</span>
                </div>
                <div className="text-green-400/80 flex items-center gap-2 text-xs">
                  <Zap className="h-3 w-3 flex-shrink-0" />
                  <span>Complete! Anything else?</span>
                </div>
              </div>
            </div>

            {/* Result */}
            <div className="mt-4 flex items-center justify-center gap-2 text-green-400 text-sm">
              <Zap className="h-4 w-4" />
              <span>Systematic. Tested. Confident.</span>
            </div>
          </div>
        </div>

        {/* Bottom highlight */}
        <div className="mt-12 text-center">
          <p className="text-muted-foreground text-sm sm:text-base max-w-2xl mx-auto">
            Claude CodePro transforms AI-assisted development from Quick Mode prompting
            into a <span className="text-primary font-medium">structured, repeatable process</span> with
            persistent memory, semantic search, enforced best practices, and automatic quality checks.
          </p>
        </div>
      </div>
    </section>
  );
};

export default ComparisonSection;
