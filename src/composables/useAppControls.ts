import type { IpcRendererLike } from '../platform/electronIpc'

export function useAppControls(ipcRenderer: IpcRendererLike | null) {
  function closeApp() {
    ipcRenderer?.send('close-app')
  }


  function openLive2DConsole() {
    ipcRenderer?.send('ui:toggleConsole')
  }

  function openAIChat() {
    ipcRenderer?.send('ui:toggleChat')
  }

  function toggleDevTools() {
    ipcRenderer?.send('ui:toggleDevTools')
  }

  return { closeApp, openLive2DConsole, openAIChat, toggleDevTools }
}
