import { useState } from "react";
import "./App.css";

const disclaimer = "This is not medical or dietary advice. Consult a qualified professional.";

function App() {
  const [ingredients, setIngredients] = useState("");
  const [locationQuery, setLocationQuery] = useState("");
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [imageDataUrl, setImageDataUrl] = useState("");
  const [imageName, setImageName] = useState("");
  const [creativity, setCreativity] = useState("balanced");
  const [responseMode, setResponseMode] = useState("concise");
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("chef_session_id");
    if (existing) return existing;
    const created = `chef-${Date.now()}`;
    localStorage.setItem("chef_session_id", created);
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

  const sendData = async () => {
    const arr = ingredients
      .split(",")
      .map((i) => i.trim())
      .filter(Boolean)
      .map((name) => ({ name }));

    if (!arr.length && !imageDataUrl) {
      setError("Please enter meal text or upload a food image.");
      setReport(null);
      return;
    }

    setLoading(true);
    setError("");
    setReport(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/assistant", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          meal_text: ingredients,
          meal_description: ingredients,
          location_query: locationQuery,
          image_data_url: imageDataUrl || null,
          creativity,
          response_mode: responseMode,
          session_id: sessionId
        })
      });

      const data = await res.json();
      if (!res.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail || data);
        throw new Error(detail || "Failed to generate meals.");
      }

      setReport(data || null);
    } catch (err) {
      setReport(null);
      setError(err.message || "Something went wrong while generating meals.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <main className="app">
        <header className="hero">
          <p className="eyebrow">Multi-Modal Nutrition AI</p>
          <h1>Nutrition Assistant</h1>
          <p className="subtitle">Drop in text, meal descriptions, or a food image and get practical nutrition guidance with structured meal support.</p>
        </header>

        <section className="controls" aria-label="Nutrition input">
          <label htmlFor="ingredients" className="input-label">Meal text or ingredients</label>
          <div className="input-row">
            <input
              id="ingredients"
              value={ingredients}
              onChange={(e) => setIngredients(e.target.value)}
              placeholder="salmon, rice, spinach or describe the meal"
            />
            <button onClick={sendData} disabled={loading}>
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </div>

          <div className="controls-grid">
            <label className="mini-field">
              <span>Creativity</span>
              <select value={creativity} onChange={(e) => setCreativity(e.target.value)}>
                <option value="strict">Strict</option>
                <option value="balanced">Balanced</option>
                <option value="creative">Creative</option>
              </select>
            </label>

            <label className="mini-field">
              <span>Response style</span>
              <select value={responseMode} onChange={(e) => setResponseMode(e.target.value)}>
                <option value="concise">Concise</option>
                <option value="detailed">Detailed</option>
              </select>
            </label>

            <label className="mini-field">
              <span>Ingredient image (optional)</span>
              <input type="file" accept="image/*" onChange={onImageSelected} />
            </label>
          </div>

          <label className="mini-field location-field">
            <span>Nearby food location</span>
            <input
              value={locationQuery}
              onChange={(e) => setLocationQuery(e.target.value)}
              placeholder="City, neighborhood, or postal code"
            />
          </label>

          {imageName && <p className="hint-text">Image loaded: {imageName}</p>}
          <p className="hint-text">Session: {sessionId}</p>
          <p className="disclaimer-banner">{disclaimer}</p>
          {error && <p className="error-text">{error}</p>}
        </section>

        {!loading && !error && !report && (
          <section className="empty-state">
            <h2>Your meal analysis will appear here</h2>
            <p>Try text like <span>"grilled chicken with rice and broccoli"</span> and optionally add a location to search nearby healthy options.</p>
          </section>
        )}

        {loading && (
          <section className="loading-state" aria-live="polite">
            <div className="pulse" />
            <p>Analyzing your meal and nearby options...</p>
          </section>
        )}

        {report && (
          <section className="report-grid" aria-label="Nutrition analysis results">
            <article className="recipe-card">
              <div className="card-top">
                <h2>Meal Analysis</h2>
              </div>
              <p className="analysis-text">{report.meal_analysis || "No analysis returned."}</p>
            </article>

            <article className="recipe-card">
              <div className="card-top">
                <h2>Nutrition Summary</h2>
              </div>
              <div className="nutrition-stats">
                <span><strong>{report?.nutrition_summary?.estimated_calories ?? "N/A"}</strong> kcal</span>
                <span><strong>{report?.nutrition_summary?.protein_g ?? "N/A"}</strong> g protein</span>
                <span><strong>{report?.nutrition_summary?.carbs_g ?? "N/A"}</strong> g carbs</span>
                <span><strong>{report?.nutrition_summary?.fat_g ?? "N/A"}</strong> g fat</span>
                <span><strong>{report?.nutrition_summary?.fiber_g ?? "N/A"}</strong> g fiber</span>
              </div>
            </article>

            <article className="recipe-card">
              <div className="card-top">
                <h2>Recommendations</h2>
              </div>
              <ul className="steps-list compact-list">
                {(report.recommendations || []).map((item, itemIndex) => (
                  <li key={`${itemIndex}-${item}`}>{item}</li>
                ))}
              </ul>
            </article>

            <article className="recipe-card">
              <div className="card-top">
                <h2>Nearby Food Search</h2>
              </div>
              {Array.isArray(report.search_results) && report.search_results.length > 0 ? (
                <ul className="search-results">
                  {report.search_results.map((item, index) => (
                    <li key={`${item.name || "result"}-${index}`}>
                      <strong>{item.name || "Nearby option"}</strong>
                      <span>{item.category || "food"}</span>
                      {item.address ? <p>{item.address}</p> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="analysis-text">No nearby search was run or no results were found.</p>
              )}
            </article>

            <article className="recipe-card">
              <div className="card-top">
                <h2>CSV Storage</h2>
              </div>
              <p className="analysis-text">
                Saved: {report?.csv_storage?.saved ? "Yes" : "No"}
                {report?.csv_storage?.path ? ` · ${report.csv_storage.path}` : ""}
              </p>
              {report?.csv_storage?.session_summary ? (
                <p className="hint-text">Session summary: {report.csv_storage.session_summary}</p>
              ) : null}
            </article>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
