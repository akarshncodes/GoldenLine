/* GoldenLine client runtime config.
 *
 * Every page loads this before its own scripts. It sets window.GOLDENLINE_API
 * to the base URL of the FastAPI backend.
 *
 * Local dev  : left as "" → the app falls back to http://localhost:8000.
 * Deployment : the static-site build (see render.yaml) overwrites this file
 *              with the real backend URL, e.g.
 *              window.GOLDENLINE_API = "https://goldenline-api.onrender.com";
 */
window.GOLDENLINE_API = "";
