const API_BASE = '/api';

async function safeFetchJson(url, options = {}) {
  try {
    const res = await fetch(url, options);
    const rawText = await res.text();
    let data;

    try {
      data = JSON.parse(rawText);
    } catch (e) {
      console.error(`[API NON-JSON RESPONSE] Status: ${res.status}, Raw text:`, rawText.slice(0, 200));
      throw new Error(`Server returned non-JSON response (Status ${res.status}): ${rawText.slice(0, 120)}`);
    }

    if (!res.ok) {
      const msg = data.error || data.detail || data.message || `Server error (${res.status})`;
      throw new Error(msg);
    }

    return data;
  } catch (err) {
    console.error(`[API FETCH FAILED] ${url}:`, err.message);
    throw err;
  }
}

export async function fetchHealth() {
  return safeFetchJson(`${API_BASE}/health`);
}

export async function fetchConfig() {
  return safeFetchJson(`${API_BASE}/config`);
}

export async function fetchSettings() {
  try {
    return await safeFetchJson(`${API_BASE}/settings`);
  } catch (err) {
    return { llmProvider: "Not configured", dockerAvailable: false };
  }
}

export async function updateSettings(settings) {
  return safeFetchJson(`${API_BASE}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings)
  });
}

export async function fetchProjects() {
  try {
    return await safeFetchJson(`${API_BASE}/projects`);
  } catch (err) {
    return [];
  }
}

export async function fetchProjectDetails(id) {
  try {
    return await safeFetchJson(`${API_BASE}/projects/${id}`);
  } catch (err) {
    return null;
  }
}

export async function createResearchProject(formData) {
  return safeFetchJson(`${API_BASE}/research`, {
    method: 'POST',
    body: formData
  });
}

export async function sendControlSignal(projectId, signal) {
  return safeFetchJson(`${API_BASE}/projects/${projectId}/control`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ signal })
  });
}

export async function fetchProjectDataset(id) {
  try {
    return await safeFetchJson(`${API_BASE}/projects/${id}/dataset`);
  } catch (err) {
    return null;
  }
}

export async function fetchProjectBaselines(id) {
  try {
    return await safeFetchJson(`${API_BASE}/projects/${id}/baselines`);
  } catch (err) {
    return [];
  }
}

export async function fetchProjectTree(id) {
  try {
    return await safeFetchJson(`${API_BASE}/projects/${id}/tree`);
  } catch (err) {
    return [];
  }
}

export async function fetchProjectErrorAnalysis(id) {
  try {
    return await safeFetchJson(`${API_BASE}/projects/${id}/error-analysis`);
  } catch (err) {
    return null;
  }
}

export async function fetchProjectLiterature(id) {
  try {
    return await safeFetchJson(`${API_BASE}/projects/${id}/literature`);
  } catch (err) {
    return [];
  }
}

export async function fetchProjectReport(id) {
  try {
    const data = await safeFetchJson(`${API_BASE}/projects/${id}/report`);
    return data ? data.report : null;
  } catch (err) {
    return null;
  }
}
