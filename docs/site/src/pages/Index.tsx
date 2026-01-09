import NavBar from "@/components/NavBar";
import HeroSection from "@/components/HeroSection";
import ComparisonSection from "@/components/ComparisonSection";
import WorkflowSteps from "@/components/WorkflowSteps";
import WhatsInside from "@/components/WhatsInside";
import InstallSection from "@/components/InstallSection";
import RequirementsSection from "@/components/RequirementsSection";
import FAQ from "@/components/FAQ";
import Footer from "@/components/Footer";
import SEO from "@/components/SEO";

const Index = () => {
  const faqStructuredData = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {
        "@type": "Question",
        "name": "What is Claude CodePro?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Claude CodePro is a professional development environment for Claude Code. It provides automated context management, spec-driven development, TDD enforcement, persistent memory, semantic search, quality hooks, and a modular rules system."
        }
      },
      {
        "@type": "Question",
        "name": "What is Endless Mode?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Endless Mode removes the 200K context limit. When context nears the limit, it automatically saves state and continues in a new session - zero manual intervention. Works in both Spec-Driven and Quick modes."
        }
      },
      {
        "@type": "Question",
        "name": "Is Claude CodePro free?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Yes! Claude CodePro is completely free and open source under the AGPL-3.0 license."
        }
      },
      {
        "@type": "Question",
        "name": "What IDEs are supported?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Claude CodePro works with VS Code, Cursor, Windsurf, and Antigravity. Any IDE with Dev Containers extension support should work."
        }
      },
      {
        "@type": "Question",
        "name": "Do I need Docker?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Yes, you need a container runtime like Docker Desktop or OrbStack (macOS). Claude CodePro runs inside a Dev Container for complete isolation and cross-platform compatibility."
        }
      },
      {
        "@type": "Question",
        "name": "What are the two development modes?",
        "acceptedAnswer": {
          "@type": "Answer",
          "text": "Spec-Driven Mode (/spec) creates a plan for your approval before implementation - great for new features. Quick Mode lets you just chat for bug fixes and small changes. Both modes get Endless Mode and TDD enforcement."
        }
      }
    ]
  };

  const breadcrumbStructuredData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": "https://www.claude-code.pro"
      }
    ]
  };

  const softwareStructuredData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "Claude CodePro",
    "description": "Professional Development Environment for Claude Code - Automated Context Management, Spec-Driven Development, Skills, TDD, LSP, Semantic Search, Persistent Memory, Quality Hooks, and Modular Rules System.",
    "applicationCategory": "DeveloperApplication",
    "operatingSystem": "Linux, macOS, Windows (via Docker)",
    "offers": {
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD"
    },
    "author": {
      "@type": "Person",
      "name": "Max Ritter",
      "url": "https://maxritter.net/"
    },
    "license": "https://www.gnu.org/licenses/agpl-3.0",
    "url": "https://github.com/maxritter/claude-codepro",
    "downloadUrl": "https://github.com/maxritter/claude-codepro"
  };

  return (
    <>
      <SEO
        title="Claude CodePro - Professional Development Environment for Claude Code"
        description="Start shipping systematically with Automated Context Management, Spec-Driven Development, Skills, TDD, LSP, Semantic Search, Persistent Memory, Quality Hooks, and more. Free and open source."
        structuredData={[faqStructuredData, breadcrumbStructuredData, softwareStructuredData]}
      />
      <NavBar />
      <main className="min-h-screen bg-background">
        <HeroSection />
        <ComparisonSection />
        <WhatsInside />
        <WorkflowSteps />
        <InstallSection />
        <RequirementsSection />
        <FAQ />
        <Footer />
      </main>
    </>
  );
};

export default Index;
