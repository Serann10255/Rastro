/// <reference types="vite/client" />

// Un guion de sustentación importado llega ya compilado: lo transforma
// `compilador/plugin.ts` al construir.
declare module "*.md" {
  const deck: import("./deck/tipos").Deck;
  export default deck;
}
