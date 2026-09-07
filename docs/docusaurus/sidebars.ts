import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebars: SidebarsConfig = {
  docsSidebar: [
    "intro",
    {
      type: "category",
      label: "Getting Started",
      collapsed: false,
      items: [
        "getting-started/prerequisites",
        "getting-started/installation",
        "getting-started/codex-cli",
      ],
    },
    {
      type: "category",
      label: "Engineering Harness",
      collapsed: false,
      items: [
        "features/hooks",
        "features/rules",
        "features/context-optimization",
        "features/knowledge",
        "features/team-memories",
      ],
    },
    {
      type: "category",
      label: "Pilot Workflows",
      collapsed: false,
      items: [
        "workflows/spec",
        "workflows/build",
        "workflows/fix",
        "workflows/prd",
        "workflows/investigate",
        "workflows/cleanup",
        "workflows/ui-design",
        "workflows/setup-rules",
        "workflows/create-skill",
        "workflows/benchmark",
      ],
    },
    {
      type: "category",
      label: "Console",
      collapsed: false,
      items: [
        "features/console",
        "features/spec-collaboration",
        "features/extensions",
        "features/customization",
        "features/statusline",
      ],
    },
    {
      type: "category",
      label: "Tools",
      collapsed: false,
      items: [
        "features/cli",
        "features/mcp-servers",
        "features/language-servers",
        "features/open-source-tools",
      ],
    },
    {
      type: "category",
      label: "Automation",
      collapsed: false,
      items: [
        "features/remote-control",
      ],
    },
    {
      type: "category",
      label: "Configuration",
      collapsed: false,
      items: [
        "features/model-routing",
        "features/permission-modes",
      ],
    },
  ],
};

export default sidebars;
