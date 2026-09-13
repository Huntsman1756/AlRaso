export const POI_CATS = {
  refuge: { emoji: "🏠", label: "Refugio", anonymousLabel: "Refugio", color: "#b45309" },
  shelter: { emoji: "🛖", label: "Abrigo / cabaña", anonymousLabel: "Abrigo", color: "#f97316" },
  water: { emoji: "💧", label: "Agua", anonymousLabel: "Agua", color: "#0ea5e9" },
  camping: { emoji: "⛺", label: "Camping / bivouac", anonymousLabel: "Camping", color: "#16a34a" },
  protected_area: { emoji: "🌲", label: "Referencia OSM: espacio natural protegido", color: "#0d9488" },
};
// protected_area queda en el snapshot (provenance) pero NO se renderiza ni es
// interactivo: un centroide de relación de parque no es un destino del usuario.
export const POI_ORDER = ["refuge", "shelter", "water", "camping"];
