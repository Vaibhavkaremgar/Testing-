import express from 'express'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const distDir = path.join(__dirname, 'dist')
const indexFile = path.join(distDir, 'index.html')
const publicJobsBaseUrl =
  process.env.VITE_PUBLIC_JOBS_BASE_URL ||
  'https://efficient-curiosity-production-a012.up.railway.app'
const port = Number.parseInt(process.env.PORT || '3000', 10)

const app = express()

app.use((req, res, next) => {
  if (req.path === '/' || req.path.endsWith('.html')) {
    res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate')
    res.setHeader('Pragma', 'no-cache')
    res.setHeader('Expires', '0')
  }
  next()
})

// Redirect public job links at the server layer before SPA fallback.
app.get('/jobs/*', (req, res) => {
  const targetUrl = `${publicJobsBaseUrl}${req.originalUrl}`
  res.redirect(302, targetUrl)
})

app.use(
  express.static(distDir, {
    index: false,
    maxAge: '7d',
    immutable: true,
  })
)

app.get('*', (_req, res) => {
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate')
  res.setHeader('Pragma', 'no-cache')
  res.setHeader('Expires', '0')
  res.sendFile(indexFile)
})

app.listen(port, '0.0.0.0', () => {
  console.log(`Frontend server listening on port ${port}`)
})
