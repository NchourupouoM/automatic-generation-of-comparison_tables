/** Tailwind config used to compile app/static/tailwind.css. */
module.exports = {
  darkMode: "class",
  content: ["./app/static/**/*.{html,js}"],
  theme: { extend: { fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] } } },
};
