# Quick Fix Reference - Railway Vite Build Errors

## Problem
```
Failed to resolve import "@/lib/api"
Failed to resolve import "@/lib/utils"
```

## Solution Applied ✅

### Updated `frontend/vite.config.js`:

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },
  server: {
    allowedHosts: ["athletic-elegance-production-ef72.up.railway.app"],
  },
});
```

## Key Changes

1. ✅ **ESM-compatible imports**: `fileURLToPath`, `dirname`, `resolve`
2. ✅ **Explicit `__dirname`**: Required for ES modules
3. ✅ **Named imports**: More reliable than default `path` import
4. ✅ **Relative path**: `"./src"` instead of `"src"`

## Test Locally

```bash
cd frontend
npm run build
```

Should see: `✓ built in [time]` with NO errors

## Deploy to Railway

```bash
git add frontend/vite.config.js
git commit -m "fix: ESM-compatible Vite config for Railway"
git push
```

## Why This Works

- Railway uses strict ESM module resolution
- `__dirname` doesn't exist in ES modules by default
- `fileURLToPath` + `dirname` creates ESM-compatible `__dirname`
- Named imports are more reliable in production builds

---

**Status:** ✅ FIXED
**Tested:** Local build ✓
**Ready for:** Railway deployment
