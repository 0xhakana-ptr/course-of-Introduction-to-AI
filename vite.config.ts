import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import electron from 'vite-plugin-electron'

export default defineConfig({
  plugins: [
    vue(),
    electron([
      {
        entry: 'electron/main.ts',
        vite: {
          build: {
            rollupOptions: {
              external: ['ws'],
            },
          },
        },
        onstart(options) {
          // Clear ELECTRON_RUN_AS_NODE injected by VS Code terminal,
          // otherwise electron.exe runs as plain Node.js instead of Electron.
          options.startup(['.', '--no-sandbox'], {
            env: { ...process.env, ELECTRON_RUN_AS_NODE: undefined },
          })
        },
      },
    ]),
  ],
})