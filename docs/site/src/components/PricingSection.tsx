import { useEffect } from "react";
import { Check, Building2, Sparkles, Calendar, Mail, RefreshCw, Zap, Shield, CircleUserRound } from "lucide-react";
import { PolarEmbedCheckout } from "@polar-sh/checkout/embed";
import { Button } from "@/components/ui/button";
import { useInView } from "@/hooks/use-in-view";
import { PORTAL_URL } from "@/lib/links";

const SOLO_CHECKOUT_URL =
  import.meta.env.VITE_POLAR_CHECKOUT_SOLO ||
  "https://buy.polar.sh/polar_cl_nxoqkuI0m3K60V4EpyaruDdPsd7CjS4jalKqc4TszL3";
const TEAM_CHECKOUT_URL =
  import.meta.env.VITE_POLAR_CHECKOUT_TEAM ||
  "https://buy.polar.sh/polar_cl_y5uSffkVLnESyfzfOSJ1M9YmMd8sIpcT7bza82oFv4C";
const IS_PRODUCTION =
  import.meta.env.PROD &&
  !import.meta.env.VITE_POLAR_PORTAL_URL?.includes("sandbox");

const PricingSection = () => {
  const [headerRef, headerInView] = useInView<HTMLDivElement>();
  const [cardsRef, cardsInView] = useInView<HTMLDivElement>();

  const soloUrl = SOLO_CHECKOUT_URL;
  const teamUrl = TEAM_CHECKOUT_URL;

  useEffect(() => {
    if (IS_PRODUCTION) {
      PolarEmbedCheckout.init();
    }
  }, []);

  return (
    <section
      id="pricing"
      className="py-16 lg:py-24 px-4 sm:px-6 relative"
      aria-labelledby="pricing-heading"
    >
      <div className="max-w-6xl mx-auto">
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

        {/* Header */}
        <div
          ref={headerRef}
          className={`text-center mb-12 ${headerInView ? "animate-fade-in-up" : "opacity-0"}`}
        >
          <h1
            id="pricing-heading"
            className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground mb-4"
          >
            Always up-to-date. Always optimized.
          </h1>
          <p className="text-muted-foreground text-lg sm:text-xl max-w-2xl mx-auto">
            Your shortcut to state-of-the-art AI-assisted development.
          </p>
        </div>

        {/* Value propositions */}
        <div className={`grid sm:grid-cols-3 gap-6 max-w-4xl mx-auto mb-16 ${headerInView ? "animate-fade-in-up animation-delay-100" : "opacity-0"}`}>
          <div className="text-center space-y-2">
            <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center mx-auto">
              <RefreshCw className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-sm font-semibold text-foreground">Continuously updated</h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              New tools, optimizations, and best practices from daily production usage — shipped as updates, not blog posts.
            </p>
          </div>
          <div className="text-center space-y-2">
            <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center mx-auto">
              <Zap className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-sm font-semibold text-foreground">Ready to use</h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Install once, get a complete AI coding setup instantly. No hours of configuration, research, or trial and error.
            </p>
          </div>
          <div className="text-center space-y-2">
            <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center mx-auto">
              <Shield className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-sm font-semibold text-foreground">Battle-tested</h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Every rule, hook, and workflow is proven in production before it ships. You get what works, not what sounds good.
            </p>
          </div>
        </div>

        <div ref={cardsRef} className="grid md:grid-cols-2 gap-6 sm:gap-8 max-w-4xl mx-auto">
          {/* Solo - Featured */}
          <div
            className={`group relative rounded-lg p-4 sm:p-6 md:p-8 border-2 border-primary/50 bg-card
              hover:border-primary hover:bg-card hover:border-primary
              transition-all duration-300 scale-[1.02] flex flex-col
              ${cardsInView ? "animate-fade-in-up animation-delay-0" : "opacity-0"}`}
          >
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-primary to-transparent" />
            <div className="flex items-center gap-3 mb-4">
              <div
                className="w-12 h-12 bg-primary/20 rounded-xl flex items-center justify-center
                group-hover:bg-primary/30 group-hover:scale-110 transition-all duration-300"
              >
                <Check className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-foreground">Solo</h2>
                <p className="text-xs text-muted-foreground">1 developer</p>
              </div>
            </div>

            <div className="mb-6">
              <span className="text-4xl font-bold text-foreground">$14</span>
              <span className="text-muted-foreground">/month</span>
            </div>

            <ul className="space-y-3 mb-8 flex-1">
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Rules, hooks, standards, LSPs, MCPs
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Pilot workflows, persistent memory, browser dashboard
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Cross-machine skill sync — push/pull skills across all your machines
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Community support via GitHub Issues
                </span>
              </li>
            </ul>

            <Button asChild className="w-full">
              <a
                href={soloUrl}
                {...(IS_PRODUCTION
                  ? {
                      "data-polar-checkout": true,
                      "data-polar-checkout-theme": "dark",
                    }
                  : { target: "_blank", rel: "noopener" })}
              >
                Subscribe
              </a>
            </Button>
          </div>

          {/* Team */}
          <div
            className={`group relative rounded-lg p-4 sm:p-6 md:p-8 border border-border/50 bg-card
              hover:border-indigo-500/50 hover:bg-card hover:border-indigo-500/50
              transition-all duration-300 flex flex-col
              ${cardsInView ? "animate-fade-in-up animation-delay-100" : "opacity-0"}`}
          >
            <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-indigo-500 to-transparent" />
            <div className="flex items-center gap-3 mb-4">
              <div
                className="w-12 h-12 bg-indigo-500/15 rounded-xl flex items-center justify-center
                group-hover:bg-indigo-500/25 group-hover:scale-110 transition-all duration-300"
              >
                <Building2 className="h-6 w-6 text-indigo-500" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-foreground">Team</h2>
                <p className="text-xs text-muted-foreground">Multiple developers</p>
              </div>
            </div>

            <div className="mb-6">
              <span className="text-4xl font-bold text-foreground">$35</span>
              <span className="text-muted-foreground">/seat/month</span>
            </div>

            <ul className="space-y-3 mb-8 flex-1">
              <li className="flex items-start gap-3">
                <Sparkles className="h-5 w-5 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Everything in Solo
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Extension sharing — share skills, rules, commands, and agents via git
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Memory sharing — store project memories in the repo so every contributor gets them
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Customization — modify Pilot's built-in skills, rules, and auto-applied settings
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Seat management — assign and manage all seats for your team in the portal
                </span>
              </li>
              <li className="flex items-start gap-3">
                <Check className="h-5 w-5 text-indigo-500 flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground text-sm group-hover:text-foreground/80 transition-colors">
                  Priority support — direct support on issues and feature requests
                </span>
              </li>
            </ul>

            <Button
              asChild
              variant="outline"
              className="w-full border-indigo-500/50 hover:bg-indigo-500/10"
            >
              <a href={teamUrl} target="_blank" rel="noopener">
                Subscribe
              </a>
            </Button>
          </div>

        </div>

        <p className="text-center text-sm text-muted-foreground mt-6">
          All plans work across multiple personal machines — one subscription,
          all your devices.
        </p>

        {/* Existing subscribers: seat changes, invoices, license key recovery */}
        <div className="mt-10 max-w-4xl mx-auto rounded-lg border border-border/50 bg-card p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
          <div className="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center flex-shrink-0">
            <CircleUserRound className="h-6 w-6 text-primary" />
          </div>
          <div className="flex-1">
            <h2 className="text-base font-semibold text-foreground mb-1">
              Already subscribed?
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Add or remove team seats, update your payment method, download
              invoices, and recover your license key in the customer portal.
              Sign in with the email you used at checkout.
            </p>
          </div>
          <Button asChild variant="outline" className="w-full sm:w-auto flex-shrink-0">
            <a href={PORTAL_URL} target="_blank" rel="noopener noreferrer">
              Manage Subscription
            </a>
          </Button>
        </div>

        {/* Rolling out for your team */}
        <div className="mt-16 text-center max-w-3xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground mb-3">
            Rolling Out for Your Team?
          </h2>
          <p className="text-muted-foreground text-base sm:text-lg mb-6">
            Let's find the right setup for your team and get everyone onboarded.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button size="lg" asChild>
              <a
                href="https://calendly.com/rittermax/pilot-shell"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Calendar className="mr-2 h-4 w-4" />
                Book a Call
              </a>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <a href="mailto:mail@maxritter.net">
                <Mail className="mr-2 h-4 w-4" />
                Send a Message
              </a>
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default PricingSection;
