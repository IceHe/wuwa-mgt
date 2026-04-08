#!/usr/bin/env node

const http = require('http')
const fs = require('fs')
const path = require('path')

const BACKEND_BASE = 'http://127.0.0.1:8765'
const BACKEND_ORIGIN = new URL(BACKEND_BASE)
const DIST_DIR = '/root/wuwa/mgt/frontend/dist'
const HOST = '0.0.0.0'
const PORT = 3001

const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
}

function setCorsHeaders(res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Token')
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS')
}

function isApiPath(urlPath) {
  return urlPath === '/api' || urlPath.startsWith('/api/')
}

function writeText(res, statusCode, body) {
  const content = Buffer.from(body, 'utf8')
  setCorsHeaders(res)
  res.writeHead(statusCode, {
    'Content-Type': 'text/plain; charset=utf-8',
    'Content-Length': String(content.length),
  })
  res.end(content)
}

function forwardToBackend(req, res) {
  const headers = {}
  const contentType = (req.headers['content-type'] || '').trim()
  const authorization = (req.headers.authorization || '').trim()
  const xToken = (req.headers['x-token'] || '').trim()

  if (contentType) headers['Content-Type'] = contentType
  if (authorization) headers.Authorization = authorization
  if (xToken) headers['X-Token'] = xToken

  const proxyReq = http.request(
    {
      protocol: BACKEND_ORIGIN.protocol,
      hostname: BACKEND_ORIGIN.hostname,
      port: BACKEND_ORIGIN.port,
      method: req.method,
      path: req.url,
      headers,
    },
    (proxyRes) => {
      const chunks = []
      proxyRes.on('data', (chunk) => chunks.push(chunk))
      proxyRes.on('end', () => {
        const body = Buffer.concat(chunks)
        setCorsHeaders(res)
        res.writeHead(proxyRes.statusCode || 502, {
          'Content-Type': proxyRes.headers['content-type'] || 'application/json; charset=utf-8',
          'Content-Length': String(body.length),
        })
        res.end(body)
      })
    },
  )

  proxyReq.on('error', (err) => {
    writeText(res, 502, String(err.message || err))
  })

  req.on('data', (chunk) => proxyReq.write(chunk))
  req.on('end', () => proxyReq.end())
  req.on('error', (err) => {
    proxyReq.destroy(err)
  })
}

function safeResolve(requestPath) {
  const cleanPath = decodeURIComponent(requestPath.split('?')[0])
  const relPath = cleanPath === '/' ? '/index.html' : cleanPath
  const resolved = path.resolve(DIST_DIR, `.${relPath}`)
  if (!resolved.startsWith(path.resolve(DIST_DIR))) return null
  return resolved
}

function serveFile(filePath, res) {
  fs.stat(filePath, (statErr, stat) => {
    if (statErr || !stat.isFile()) {
      serveSpaEntry(res)
      return
    }
    const ext = path.extname(filePath).toLowerCase()
    const contentType = MIME_TYPES[ext] || 'application/octet-stream'
    setCorsHeaders(res)
    res.writeHead(200, {
      'Content-Type': contentType,
      'Content-Length': String(stat.size),
    })
    const stream = fs.createReadStream(filePath)
    stream.on('error', () => writeText(res, 500, 'failed to read file'))
    stream.pipe(res)
  })
}

function serveSpaEntry(res) {
  const indexPath = path.join(DIST_DIR, 'index.html')
  fs.readFile(indexPath, (err, data) => {
    if (err) {
      writeText(res, 500, 'frontend dist is missing')
      return
    }
    setCorsHeaders(res)
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Content-Length': String(data.length),
    })
    res.end(data)
  })
}

const server = http.createServer((req, res) => {
  const urlPath = req.url || '/'

  if (req.method === 'OPTIONS') {
    setCorsHeaders(res)
    res.writeHead(200)
    res.end()
    return
  }

  if (isApiPath(urlPath)) {
    forwardToBackend(req, res)
    return
  }

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    writeText(res, 405, 'method not allowed')
    return
  }

  const filePath = safeResolve(urlPath)
  if (!filePath) {
    writeText(res, 400, 'invalid path')
    return
  }
  serveFile(filePath, res)
})

server.on('clientError', () => {
  // Ignore malformed client sockets.
})

server.listen(PORT, HOST)
