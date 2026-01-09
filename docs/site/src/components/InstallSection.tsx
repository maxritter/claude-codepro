import { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";

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

const InstallSection = () => {
  const [copied, setCopied] = useState(false);
  const installCommand = "curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/main/install.sh | bash";

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="installation" className="py-20 lg:py-28 px-4 sm:px-6 bg-card/30">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
      <div className="max-w-4xl mx-auto">
        <SectionHeader
          title="One-Command Installation"
          subtitle="Install Claude CodePro into any existing project in seconds"
        />

        {/* Install command */}
        <div className="glass rounded-2xl p-6 sm:p-8 relative overflow-hidden glow-primary mb-8">
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent" />

          <div className="flex items-center gap-2 mb-4">
            <Terminal className="h-5 w-5 text-primary" />
            <span className="text-foreground font-semibold text-sm sm:text-base">
              Run in your project directory:
            </span>
          </div>

          <div className="bg-background/50 rounded-lg p-3 sm:p-4 font-mono text-sm overflow-hidden">
            <div className="flex items-center justify-between gap-2 sm:gap-4">
              <code className="text-muted-foreground truncate min-w-0 text-xs sm:text-sm">
                <span className="text-primary">$</span> {installCommand}
              </code>
              <Button
                variant="ghost"
                size="sm"
                onClick={copyToClipboard}
                className="flex-shrink-0 hover:bg-primary/10"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-500" />
                ) : (
                  <Copy className="h-4 w-4 text-muted-foreground" />
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Steps */}
        <div className="space-y-4">
          <div className="glass rounded-xl p-4 sm:p-5">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 bg-primary/15 rounded-lg flex items-center justify-center text-primary font-bold text-sm flex-shrink-0">
                1
              </div>
              <div>
                <h4 className="text-foreground font-semibold text-sm sm:text-base mb-1">
                  Open your project in your IDE
                </h4>
                <p className="text-muted-foreground text-xs sm:text-sm">
                  Works with VS Code, Cursor, Windsurf, or Antigravity
                </p>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-4 sm:p-5">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 bg-primary/15 rounded-lg flex items-center justify-center text-primary font-bold text-sm flex-shrink-0">
                2
              </div>
              <div>
                <h4 className="text-foreground font-semibold text-sm sm:text-base mb-1">
                  Run the install command in terminal
                </h4>
                <p className="text-muted-foreground text-xs sm:text-sm">
                  The script will set up the Dev Container configuration
                </p>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-4 sm:p-5">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 bg-primary/15 rounded-lg flex items-center justify-center text-primary font-bold text-sm flex-shrink-0">
                3
              </div>
              <div>
                <h4 className="text-foreground font-semibold text-sm sm:text-base mb-1">
                  Reopen in Container
                </h4>
                <p className="text-muted-foreground text-xs sm:text-sm">
                  <code className="text-primary text-xs">Cmd+Shift+P</code> → "Dev Containers: Reopen in Container"
                </p>
              </div>
            </div>
          </div>

          <div className="glass rounded-xl p-4 sm:p-5">
            <div className="flex items-start gap-4">
              <div className="w-8 h-8 bg-primary/15 rounded-lg flex items-center justify-center text-primary font-bold text-sm flex-shrink-0">
                4
              </div>
              <div>
                <h4 className="text-foreground font-semibold text-sm sm:text-base mb-1">
                  Start building
                </h4>
                <p className="text-muted-foreground text-xs sm:text-sm">
                  Run <code className="text-primary text-xs">ccp</code>, then <code className="text-primary text-xs">/setup</code> once, then <code className="text-primary text-xs">/spec "task"</code> or just chat
                </p>
              </div>
            </div>
          </div>
        </div>

        <p className="text-center text-muted-foreground mt-8 text-xs sm:text-sm">
          <strong className="text-foreground">Cursor, Windsurf, Antigravity users:</strong> After container starts, run the install command again as these IDEs don't auto-execute postCreateCommand.
        </p>
      </div>
    </section>
  );
};

export default InstallSection;
