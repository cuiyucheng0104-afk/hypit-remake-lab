import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Single self-contained index.html (JS/CSS inlined) so LAN browsers need nothing from the internet.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: { outDir: '../hypit_studio/web', emptyOutDir: true },
  server: { proxy: { '/studio/api': 'http://127.0.0.1:18188', '/upload': 'http://127.0.0.1:18188', '/view': 'http://127.0.0.1:18188' } },
})
