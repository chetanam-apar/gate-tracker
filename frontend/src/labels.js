// Turns code names into nice names for the screen.

export const PLATFORM_NAMES = {
  appstore: "App Store",
  playstore: "Play Store",
  roblox: "Roblox",
};

export const DEVICE_NAMES = {
  all: "All devices",
  computer: "Computer",
  high_end_phone: "Phone",
  low_end_phone: "Entry-level phone",
  high_end_tablet: "Tablet",
  low_end_tablet: "Entry-level tablet",
  console: "Console",
  vr: "VR",
};

// "top_trending" -> "Top trending", "trending_in_rpg" -> "Trending in RPG"
export function chartName(chart) {
  const text = chart.replaceAll("_", " ");
  return (text.charAt(0).toUpperCase() + text.slice(1)).replace(/\brpg\b/i, "RPG");
}

export function formatNumber(n) {
  return n == null ? "-" : n.toLocaleString("en-IN");
}

export function formatDateTime(iso) {
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}
