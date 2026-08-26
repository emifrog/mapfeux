import path from 'node:path';

import { defineConfig } from 'vitest/config';

// L'alias `@/` de tsconfig, que Vitest ne lit pas tout seul : sans lui, un
// test ne peut importer que ce qui n'importe rien — le premier module testé
// à travers l'alias l'a révélé.
export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
});
