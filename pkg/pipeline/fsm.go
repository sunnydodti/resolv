package pipeline

// FSM stages: Analyze → Plan → Apply → Build/Test → Review → Publish → Record
// Failures: Build/Test back to Apply; Review back to Analyze; exhaustion → Draft PR + gaps
