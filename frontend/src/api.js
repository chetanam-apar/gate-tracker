// All calls to the backend API live in this one file.
// Pages never write "/api/..." themselves. If an address changes, we fix it only here.

async function get(path) {
  const response = await fetch(path);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      message = (await response.json()).detail || message;
    } catch {
      // the error had no JSON body, keep the status text
    }
    throw new Error(message);
  }
  return response.json();
}

// Builds "?device=computer&date=2026-11-24", skipping empty values and device "all"
function query(params) {
  const parts = Object.entries(params)
    .filter(([key, value]) => value != null && value !== "" && !(key === "device" && value === "all"))
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export const api = {
  health: () => get("/api/health"),
  charts: () => get("/api/charts"),
  chart: (platform, chart, device, date) => get(`/api/charts/${platform}/${chart}${query({ device, date })}`),
  chartDates: (platform, chart, device) => get(`/api/charts/${platform}/${chart}/dates${query({ device })}`),
  robloxGenres: (chart, device, days) => get(`/api/roblox/genres${query({ chart, device, days })}`),
  runs: () => get("/api/runs"),
};
