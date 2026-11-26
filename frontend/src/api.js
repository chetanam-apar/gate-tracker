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

export const api = {
  health: () => get("/api/health"),
  charts: () => get("/api/charts"),
  chart: (platform, chart, device) => {
    const query = device && device !== "all" ? `?device=${encodeURIComponent(device)}` : "";
    return get(`/api/charts/${platform}/${chart}${query}`);
  },
  runs: () => get("/api/runs"),
};
