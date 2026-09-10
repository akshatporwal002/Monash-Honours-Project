# Native browsers and Safari

NFR18 requires current test-time Chrome, Edge, Firefox and Safari. Record version
and update channel from each browser's About screen on the test date; do not copy
the audit's versions. Record OS build, hardware, viewport, scaling, zoom, input
device and assistive technology in [environment records](result-templates.md).
Run the [role matrix](role-matrix.md) for each browser, with fresh fixture records
for each mutating branch. Record omissions; one engine does not cover another.

## Native Safari on a Mac

1. Allocate a Mac with a supported macOS/Safari combination, the exact test checkout
   and coordinator-prepared dependencies. Start the [local setup](setup.md) there
   using reserved localhost ports. A separate Windows server's `127.0.0.1` is not
   the Mac's localhost. If local Mac setup is unavailable, have the coordinator
   provide an approved synthetic test host and record its origin/configuration;
   do not expose fixture endpoints publicly or disable origin/security controls.
2. Launch the installed **Safari app**. Capture Safari → About Safari and macOS
   version/build. Standard stable Safari is the primary result; Safari Technology
   Preview, Playwright WebKit and device emulation are separately labelled evidence.
3. Open a fresh Private Window, then `/login`. Record whether privacy/content-blocker
   settings differ from default. Test normal-mode behaviour too if private browsing
   changes authentication. Do not reuse another role's cookies; sign out or close
   all private windows between roles (private tabs can share sessions).
4. For a complete keyboard pass, enable Safari Settings → Advanced → “Press Tab
   to highlight each item on a web page”; record macOS Keyboard navigation setting
   too. Test with the pointer set aside. This Safari setting and Option-Tab behaviour
   are documented by [Apple](https://support.apple.com/en-au/guide/safari/ibrw1075/mac),
   checked 10 September 2026. Record any changed menu names on the installed version.
5. Run G01/G02, then all student, educator, assessor and admin matrix rows. Include
   file picker/upload, select/popover interaction, save/reload, confirmation/cancel,
   assessment result/review, circuit simulation/text, worker feedback and errors.
6. Turn on VoiceOver with Command-F5 (or the Mac's configured accessibility shortcut).
   Record Quick Nav and verbosity settings. Use headings/landmarks and forms/table
   navigation with a human VoiceOver user; run procedure S and save actual speech.
7. Use Safari's page zoom controls for 200% and 400%, recording the displayed setting
   and actual layout width. Disable Zoom Text Only for the native page-zoom pass if
   that option is enabled. Perform text-only enlargement separately if desired.
   Follow V for unsupported zoom levels and reflow; pinch magnification alone does
   not establish the required layout reflow.
8. Save native screenshots including browser chrome/zoom indicator, short recordings
   where permitted, and redacted console/network details for failures. Identify
   Safari-specific differences and reproducibility after a fresh fixture.

The Windows preparation in this assignment cannot supply native Safari evidence.
Until a real Mac tester fills the records, its result remains blank. Neither a
Playwright WebKit pass nor an AI walkthrough is a first-time human usability trial.
