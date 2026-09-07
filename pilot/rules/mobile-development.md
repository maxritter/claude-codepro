---
paths:
  - "**/capacitor.config.*"
  - "**/ionic.config.json"
  - "**/android/app/build.gradle*"
  - "**/android/app/src/main/AndroidManifest.xml"
  - "**/*.xcodeproj/project.pbxproj"
  - "**/*.xcworkspace/contents.xcworkspacedata"
  - "**/Podfile"
  - "**/pubspec.yaml"
  - "**/react-native.config.*"
  - "**/metro.config.*"
  - "**/expo.json"
  - "**/app.config.{js,ts}"
---

## Mobile Development

Use the project's build, install, signing, device, and verification instructions. Read relevant project rules before choosing a generic driver or command. Confirm actual bundle/package ids, SDK/toolchain pins, target devices, and build variants; do not guess them.

### Verify the installed app

For changes that affect native integration, packaging, permissions, or release behaviour, build and exercise the installed app. A desktop dev server does not prove the native artifact works. Record the build identity and whether it was a simulator/emulator or physical device.

Choose a supported driver for the actual surface:

| Surface | Verification approach |
|---------|-----------------------|
| Android WebView | The project's WebView/CDP bridge when debugging is available, or its UI automation harness |
| Android native | The project's supported accessibility/UI automation driver |
| iOS WebView | The project's supported Web Inspector/WebView bridge or native UI automation harness |
| iOS native | The project's XCTest/accessibility/device automation harness |

Inspect current driver capabilities. Reading and acting may use different tools; selectors, accessibility identifiers, and screenshots each have limits. Prefer stable selectors/identifiers when available and use fresh screenshots/bounds for coordinate interactions. A desktop browser driver cannot be assumed to reach a mobile WebView.

### Debugging and device state

- For Android WebView debugging, identify the target package/process and its actual debugging socket before forwarding a port. Do not pick the first socket on a device with multiple apps. Revalidate the forward after a process restart.
- Debugging availability depends on the build and framework. Keep remote debugging and injected bridges out of production builds; use the project's documented development gates.
- For iOS, use a driver explicitly supporting that platform and WebView; do not assume desktop Chrome CDP applies.
- An Android `INSTALL_FAILED_VERSION_DOWNGRADE` means the artifact's version code is below the installed one. Use the documented test-build path and preserve app data; do not uninstall, reset data, or change release versioning merely to bypass it.
- Poll device boot, app readiness, and asynchronous work with a timeout. Do not wait indefinitely.
- Keyboard-dismiss actions can behave as BACK or navigation. Inspect the resulting screen before assuming the app crashed.
- Clear or replace app state only when authorized for the selected test target. Preserve inputs and user data during an ongoing workflow.

### Device-specific UI checks

Use the interaction and advisory detector guidance in `browser-automation.md`. An SPA's built HTML may be only a shell; use relevant source or a rendered view obtained through the supported driver.

Inspect relevant screen sizes, OS text scaling, keyboard-visible states, safe areas, and supported themes. On devices, check clipped content at the notch/status bar/home indicator and whether controls remain reachable.

Follow `standards-frontend.md` for WebView accessibility. Meet applicable WCAG target-size requirements and the platform's touch guidance using its own units. Existing native components and platform conventions usually provide the right baseline.

- Account for safe-area and edge-to-edge insets using the project's framework. On the web, verify viewport configuration together with `env(safe-area-inset-*)` rather than assuming an inset is present.
- Select viewport units and keyboard handling for the actual platform; `dvh` alone does not guarantee the keyboard cannot cover an action.
- Keep focused fields and primary actions usable when the keyboard opens.
- Set intentional surface/background colours and test interaction with the OS theme.
- Support text scaling without clipping, overlap, or inaccessible navigation.
