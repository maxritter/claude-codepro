import { useState } from "react";
import { Check, Copy, Terminal, Container, Laptop } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Step {
  number: number;
  title: string;
  description: string;
}

const devContainerSteps: Step[] = [
  {
    number: 1,
    title: "Choose Dev Container when prompted",
    description: "The script will set up the Dev Container configuration",
  },
  {
    number: 2,
    title: "Reopen in Container",
    description: 'Cmd+Shift+P → "Dev Containers: Reopen in Container"',
  },
  {
    number: 3,
    title: "Wait for container setup",
    description: "Dev Container installation completes automatically",
  },
  {
    number: 4,
    title: "Run install command again",
    description: "Run the curl command in container terminal to finish setup",
  },
  {
    number: 5,
    title: "Start Claude CodePro",
    description: "Run ccp to start, then /setup once to initialize",
  },
];

const localSteps: Step[] = [
  {
    number: 1,
    title: "Choose Local Installation when prompted",
    description: "Select option 2 for local Homebrew installation",
  },
  {
    number: 2,
    title: "Confirm the installation",
    description: "Review Homebrew packages, shell config, and CC config",
  },
  {
    number: 3,
    title: "Wait for installation",
    description: "Homebrew packages and tools are installed automatically",
  },
  {
    number: 4,
    title: "Reload your shell",
    description: "Run: source ~/.zshrc (or ~/.bashrc)",
  },
  {
    number: 5,
    title: "Start Claude CodePro",
    description: "Run ccp to start, then /setup once to initialize",
  },
];

const SectionHeader = ({ title, subtitle }: { title: string; subtitle?: string }) => (
  <div className="text-center mb-8">
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

interface StepsCardProps {
  title: string;
  icon: React.ElementType;
  steps: Step[];
  note?: string;
}

const StepsCard = ({ title, icon: Icon, steps, note }: StepsCardProps) => (
  <div className="glass rounded-2xl p-5 sm:p-6">
    <div className="flex items-center gap-3 mb-5">
      <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <h3 className="text-foreground font-bold text-base sm:text-lg">{title}</h3>
    </div>

    <div className="space-y-3">
      {steps.map((step) => (
        <div key={step.number} className="flex items-start gap-3">
          <div className="w-6 h-6 bg-primary/15 rounded-md flex items-center justify-center text-primary font-bold text-xs flex-shrink-0">
            {step.number}
          </div>
          <div>
            <h4 className="text-foreground font-semibold text-sm mb-0.5">
              {step.title}
            </h4>
            <p className="text-muted-foreground text-xs">
              {step.description}
            </p>
          </div>
        </div>
      ))}
    </div>

    {note && (
      <p className="text-muted-foreground text-xs mt-4 pt-3 border-t border-border/50">
        <strong className="text-foreground">Note:</strong> {note}
      </p>
    )}
  </div>
);

const InstallSection = () => {
  const [copied, setCopied] = useState(false);
  const installCommand = "curl -fsSL https://raw.githubusercontent.com/maxritter/claude-codepro/v4.5.28/install.sh | bash";

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(installCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="installation" className="py-12 lg:py-16 px-4 sm:px-6">
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
      <div className="max-w-4xl mx-auto">
        <SectionHeader
          title="One-Command Installation"
          subtitle="Install Claude CodePro into any existing project"
        />

        {/* Install command - compact */}
        <div className="glass rounded-xl p-4 relative overflow-hidden glow-primary mb-6">
          <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent" />

          <div className="flex items-center gap-2 mb-2">
            <Terminal className="h-4 w-4 text-primary" />
            <span className="text-foreground font-medium text-sm">
              Run in your project directory:
            </span>
          </div>

          <div className="bg-background/50 rounded-md p-2 font-mono text-sm">
            <div className="flex items-center justify-between gap-2">
              <code className="text-muted-foreground text-xs break-all">
                <span className="text-primary">$</span> {installCommand}
              </code>
              <Button
                variant="ghost"
                size="sm"
                onClick={copyToClipboard}
                className="flex-shrink-0 hover:bg-primary/10 h-7 w-7 p-0"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-green-500" />
                ) : (
                  <Copy className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Steps - Side by side */}
        <div className="grid md:grid-cols-2 gap-4">
          <StepsCard
            title="Dev Container (All Platforms)"
            icon={Container}
            steps={devContainerSteps}
            note="Works on macOS, Linux, and Windows (WSL2)."
          />
          <StepsCard
            title="Local (macOS/Linux)"
            icon={Laptop}
            steps={localSteps}
            note="Installs packages directly on your system."
          />
        </div>
      </div>
    </section>
  );
};

export default InstallSection;
