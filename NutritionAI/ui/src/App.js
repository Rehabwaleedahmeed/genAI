import { useState } from "react";
import "./App.css";

const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:8000";

function App() {
  const [mealText, setMealText] = useState("");
  const [agentResult, setAgentResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [imageDataUrl, setImageDataUrl] = useState("");
  const [imageName, setImageName] = useState("");
  const [doSearch, setDoSearch] = useState(true);
  const [doStore, setDoStore] = useState(true);
  const [searchQuery, setSearchQuery] = useState("healthy restaurants near me");

  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("nutrition_session_id");
    if (existing) return existing;
    const created = `nutrition-${Date.now()}`;
    localStorage.setItem("nutrition_session_id", created);
    return created;
  });

  const onImageSelected = async (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      setImageDataUrl("");
      setImageName("");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      setImageDataUrl(String(reader.result || ""));
      setImageName(file.name);
    };
    reader.onerror = () => {
      setImageDataUrl("");
      setImageName("");
      setError("Could not read image file.");
    };
    reader.readAsDataURL(file);
  };

  const runAgent = async () => {
    if (!mealText.trim() && !imageDataUrl) {
      setError("Please enter meal text or upload an image.");
      setAgentResult(null);
      return;
    }

    setLoading(true);
    setError("");
    setAgentResult(null);

    try {
      const res = await fetch(`${API_BASE}/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: mealText,
          image_url: imageDataUrl || null,
          session_id: sessionId,
          do_search: doSearch,
          do_store: doStore,
          search_query: searchQuery || null
        })
      });

      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail || data);
        throw new Error(detail || "Failed to run nutrition agent.");
      }
      setAgentResult(data);
    } catch (err) {
      setAgentResult(null);
      if (String(err?.message || "").toLowerCase().includes("failed to fetch")) {
        setError(`Cannot reach backend at ${API_BASE}. Start FastAPI server on port 8001 or set REACT_APP_API_BASE_URL.`);
      } else {
        setError(err.message || "Something went wrong while running the nutrition agent.");
      }
    } finally {
      setLoading(false);
    }
  };

  const analysis = agentResult?.analysis || null;
  const items = analysis?.meal_analysis || [];
  const recommendations = analysis?.recommendations || [];
  const searchResults = Array.isArray(agentResult?.search) ? agentResult.search : [];

  return (
    <div className="page-shell">
      <main className="app">
        <header className="hero">
          <p className="eyebrow">Multi-Modal Nutrition Assistant</p>
          <h1>Nutrition AI</h1>
          <p className="subtitle">Analyze meal text or food image, optionally search healthy places, and store structured logs.</p>
        </header>

        <section className="controls" aria-label="Nutrition input">
          <label htmlFor="mealText" className="input-label">Meal Description</label>
          <div className="input-row">
            <input
              id="mealText"
              value={mealText}
              onChange={(e) => setMealText(e.target.value)}
              placeholder="e.g. grilled chicken, rice, salad"
            />
            <button onClick={runAgent} disabled={loading}>
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </div>

          <div className="controls-grid">
            <label className="mini-field">
              <span>Search query (optional)</span>
              <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            </label>

            <label className="mini-field">
              <span>
                <input type="checkbox" checked={doSearch} onChange={(e) => setDoSearch(e.target.checked)} />
                {" "}Run Search Tool
              </span>
            </label>

            <label className="mini-field">
              <span>
                <input type="checkbox" checked={doStore} onChange={(e) => setDoStore(e.target.checked)} />
                {" "}Run CSV Storage Tool
              </span>
            </label>

            <label className="mini-field">
              <span>Food image (optional)</span>
              <input type="file" accept="image/*" onChange={onImageSelected} />
            </label>
          </div>

          {imageName && <p className="hint-text">Image loaded: {imageName}</p>}
          <p className="hint-text">Session: {sessionId}</p>
          <p className="hint-text">API: {API_BASE}</p>
          {error && <p className="error-text">{error}</p>}
        </section>

        {!loading && !error && !agentResult && (
          <section className="empty-state">
            <h2>Your nutrition analysis will appear here</h2>
            <p>Try text like <span>"oatmeal, banana"</span> or include a food image.</p>
          </section>
        )}

        {loading && (
          <section className="loading-state" aria-live="polite">
            <div className="pulse" />
            <p>Running nutrition agent...</p>
          </section>
        )}

        {analysis && (
          <section className="recipes-grid" aria-label="Agent outputs">
            <article className="recipe-card">
                <div className="card-top">
                  <h2>Meal Analysis</h2>
                  <div className="meta-row">
                    <span>Total calories: {analysis?.nutrition_summary?.total_calories ?? "N/A"}</span>
                  </div>
                </div>

                <div>
                  <h3>Detected Items</h3>
                  <ul className="ingredient-chips">
                    {items.map((item, itemIndex) => (
                      <li key={`${item.name || "ingredient"}-${itemIndex}`} className="chip">
                        {item.name || "Unknown"} ({item.est_calories ?? "?"} kcal)
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h3>Recommendations</h3>
                  <ol className="steps-list">
                    {recommendations.map((step, stepIndex) => (
                      <li key={`${stepIndex}-${step}`}>{step}</li>
                    ))}
                  </ol>
                </div>

                <div>
                  <h3>Search Results</h3>
                  {searchResults.length === 0 ? (
                    <p>No search results or search not requested.</p>
                  ) : (
                    <ul className="steps-list">
                      {searchResults.map((r, i) => (
                        <li key={`${i}-${r.name}`}>{r.name}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <h3>CSV Storage</h3>
                  <p>{agentResult?.store?.status === "stored" ? `Stored to ${agentResult.store.path}` : "Storage not requested."}</p>
                </div>

                <div>
                  <h3>Safety</h3>
                  <p>{analysis.disclaimer}</p>
                </div>
            </article>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
