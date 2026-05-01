import { useState } from "react";
import "./App.css";

function App() {
  const [ingredients, setIngredients] = useState("");
  const [recipes, setRecipes] = useState([]);
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
      setError("Please enter ingredients text or upload an ingredient image.");
      setRecipes([]);
      return;
    }

    setLoading(true);
    setError("");
    setRecipes([]);

    try {
      const res = await fetch("http://127.0.0.1:8000/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          ingredients: arr,
          ingredients_text: ingredients,
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

      const normalized = Array.isArray(data?.data) ? data.data : [];
      setRecipes(normalized);
    } catch (err) {
      setRecipes([]);
      setError(err.message || "Something went wrong while generating meals.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-shell">
      <main className="app">
        <header className="hero">
          <p className="eyebrow">Smart Meal Planner</p>
          <h1>AI Chef</h1>
          <p className="subtitle">Drop in ingredients and get a practical meal plan with ready-to-cook steps.</p>
        </header>

        <section className="controls" aria-label="Recipe input">
          <label htmlFor="ingredients" className="input-label">Ingredients</label>
          <div className="input-row">
            <input
              id="ingredients"
              value={ingredients}
              onChange={(e) => setIngredients(e.target.value)}
              placeholder="chicken, rice, garlic"
            />
            <button onClick={sendData} disabled={loading}>
              {loading ? "Cooking..." : "Cook"}
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

          {imageName && <p className="hint-text">Image loaded: {imageName}</p>}
          <p className="hint-text">Session: {sessionId}</p>
          {error && <p className="error-text">{error}</p>}
        </section>

        {!loading && !error && recipes.length === 0 && (
          <section className="empty-state">
            <h2>Your recipe cards will appear here</h2>
            <p>Try ingredients like <span>"chicken, rice, onion"</span> to generate ideas.</p>
          </section>
        )}

        {loading && (
          <section className="loading-state" aria-live="polite">
            <div className="pulse" />
            <p>Building your meal ideas...</p>
          </section>
        )}

        {recipes.length > 0 && (
          <section className="recipes-grid" aria-label="Generated recipes">
            {recipes.map((recipe, index) => (
              <article className="recipe-card" key={`${recipe.meal || "meal"}-${index}`}>
                <div className="card-top">
                  <h2>{recipe.meal || "Untitled Meal"}</h2>
                  <div className="meta-row">
                    <span>{recipe.cooking_time || "Time N/A"}</span>
                    <span>{recipe.servings || "Servings N/A"}</span>
                  </div>
                </div>

                <div>
                  <h3>Ingredients</h3>
                  <ul className="ingredient-chips">
                    {(recipe.ingredients || []).map((item, itemIndex) => (
                      <li key={`${item.name || "ingredient"}-${itemIndex}`} className="chip">
                        {item.name || "Unknown"}
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h3>Instructions</h3>
                  <ol className="steps-list">
                    {(recipe.instructions || []).map((step, stepIndex) => (
                      <li key={`${stepIndex}-${step}`}>{step}</li>
                    ))}
                  </ol>
                </div>
              </article>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
