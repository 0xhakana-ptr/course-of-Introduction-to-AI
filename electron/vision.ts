// electron/vision.ts
// Vision screenshot loop extracted from electron/main.ts

import { desktopCapturer } from 'electron'
import path from 'node:path'
import fs from 'node:fs'

const VISION_SCREENSHOT_INTERVAL_MS = parseInt(process.env.VISION_INTERVAL_MS ?? '30000', 10)
const VISION_SCREENSHOT_PATH = path.join(process.cwd(), 'backend', '.tmp_cache', 'vision_screenshots', 'screenshot_latest.png')
let _visionScreenshotTimer: ReturnType<typeof setInterval> | null = null

export function startVisionScreenshotLoop() {
    if (_visionScreenshotTimer) return
    const enabled = String(process.env.VISION_ENABLED ?? 'true').trim().toLowerCase()
    if (enabled !== 'true' && enabled !== '1' && enabled !== 'yes') {
        console.log('[vision] disabled (VISION_ENABLED != true)')
        return
    }
    console.log(`[vision] screenshot loop started, interval=${VISION_SCREENSHOT_INTERVAL_MS}ms`)
    _visionScreenshotTimer = setInterval(captureAndSaveScreenshot, VISION_SCREENSHOT_INTERVAL_MS)
    // Also run once immediately
    captureAndSaveScreenshot()
}

export function stopVisionScreenshotLoop() {
    if (_visionScreenshotTimer) {
        clearInterval(_visionScreenshotTimer)
        _visionScreenshotTimer = null
        console.log('[vision] screenshot loop stopped')
    }
}

async function captureAndSaveScreenshot() {
    try {
        const sources = await desktopCapturer.getSources({
            types: ['screen'],
            thumbnailSize: { width: 640, height: 640 },
        })
        if (!sources || sources.length === 0) {
            console.warn('[vision] no screen sources found')
            return
        }
        // Use primary screen
        const primary = sources[0]
        const pngBuffer = primary.thumbnail.toPNG()

        // Ensure directory exists
        const dir = path.dirname(VISION_SCREENSHOT_PATH)
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true })
        }

        // Atomic write: write to temp then rename. The backend may hold the
        // target open for a brief read, so retry before falling back to an
        // in-place copy (readers then see a torn frame instead of losing one).
        const tmpPath = VISION_SCREENSHOT_PATH + '.tmp'
        fs.writeFileSync(tmpPath, pngBuffer)
        let renamed = false
        for (let attempt = 0; attempt < 3 && !renamed; attempt++) {
            try {
                fs.renameSync(tmpPath, VISION_SCREENSHOT_PATH)
                renamed = true
            } catch (renameErr: unknown) {
                if (attempt === 2) {
                    fs.copyFileSync(tmpPath, VISION_SCREENSHOT_PATH)
                    fs.rmSync(tmpPath, { force: true })
                } else {
                    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 150)
                    void renameErr
                }
            }
        }

        console.log(`[vision] screenshot saved: ${VISION_SCREENSHOT_PATH} (${(pngBuffer.length / 1024).toFixed(1)} KB)`)
    } catch (err) {
        console.error('[vision] screenshot failed:', err)
    }
}
