/**
 * Embedded Node.js Server for Android APK
 * This runs inside the capacitor-nodejs plugin
 */

const { channel } = require('bridge');
const http = require('http');
const https = require('https');

// Configuration
let apiKey = null;
const PORT = 3000;

// Simple in-memory rate limiter
const rateLimitStore = new Map();
const RATE_LIMIT = 100;
const WINDOW_MS = 60 * 60 * 1000;

function checkRateLimit(ip) {
  const now = Date.now();
  let data = rateLimitStore.get(ip);

  if (!data || now - data.windowStart > WINDOW_MS) {
    data = { count: 1, windowStart: now };
    rateLimitStore.set(ip, data);
    return true;
  }

  data.count++;
  return data.count <= RATE_LIMIT;
}

// Haversine distance calculation
function calculateDistance(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLng/2) * Math.sin(dLng/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return Math.round(R * c * 100) / 100;
}

// Make HTTPS request (for Google Places API)
function httpsRequest(url, options, body = null) {
  return new Promise((resolve, reject) => {
    const req = https.request(url, options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          resolve(data);
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

// Search nearby places using Google Places API (New)
async function searchNearby(lat, lng, radius, types) {
  if (!apiKey) {
    throw new Error('API key not configured');
  }

  const url = 'https://places.googleapis.com/v1/places:searchNearby';
  const body = {
    includedPrimaryTypes: types,
    maxResultCount: 20,
    locationRestriction: {
      circle: {
        center: { latitude: lat, longitude: lng },
        radius: radius
      }
    }
  };

  const options = {
    method: 'POST',
    headers: {
      'X-Goog-Api-Key': apiKey,
      'X-Goog-FieldMask': 'places.id,places.displayName,places.primaryType,places.location,places.formattedAddress,places.rating,places.userRatingCount,places.regularOpeningHours,places.googleMapsUri',
      'Content-Type': 'application/json'
    }
  };

  const response = await httpsRequest(url, options, body);
  return response.places || [];
}

// Adaptive tiling search
async function adaptiveTilingSearch(lat, lng, radiusMeters, types) {
  const MIN_RADIUS = 500;
  const MAX_DEPTH = 5;
  const seenPlaces = new Map();

  const queue = [{ lat, lng, radius: radiusMeters, depth: 0 }];
  let apiCalls = 0;

  while (queue.length > 0 && apiCalls < 200) {
    const tile = queue.shift();
    apiCalls++;

    try {
      const places = await searchNearby(tile.lat, tile.lng, tile.radius, types);

      for (const place of places) {
        if (!seenPlaces.has(place.id)) {
          seenPlaces.set(place.id, {
            id: place.id,
            name: place.displayName?.text || 'Unknown',
            type: place.primaryType,
            location: place.location,
            address: place.formattedAddress,
            rating: place.rating || 0,
            reviewCount: place.userRatingCount || 0,
            openingHours: place.regularOpeningHours?.weekdayDescriptions || [],
            googleMapsUri: place.googleMapsUri
          });
        }
      }

      // Subdivide if truncated
      if (places.length >= 20 && tile.radius > MIN_RADIUS && tile.depth < MAX_DEPTH) {
        const childRadius = tile.radius / 2;
        const offset = childRadius * 0.7 / 111320;
        const lngOffset = offset / Math.cos(tile.lat * Math.PI / 180);

        queue.push({ lat: tile.lat + offset, lng: tile.lng - lngOffset, radius: childRadius, depth: tile.depth + 1 });
        queue.push({ lat: tile.lat + offset, lng: tile.lng + lngOffset, radius: childRadius, depth: tile.depth + 1 });
        queue.push({ lat: tile.lat - offset, lng: tile.lng - lngOffset, radius: childRadius, depth: tile.depth + 1 });
        queue.push({ lat: tile.lat - offset, lng: tile.lng + lngOffset, radius: childRadius, depth: tile.depth + 1 });
      }
    } catch (err) {
      console.error('Tile search error:', err.message);
    }
  }

  return {
    places: Array.from(seenPlaces.values()),
    metrics: { apiCalls, uniquePlaces: seenPlaces.size }
  };
}

// Convert place to response format
function formatPlace(place, searchLat, searchLng) {
  const lat = place.location?.latitude || 0;
  const lng = place.location?.longitude || 0;

  let openingHours = place.openingHours || [];
  if (openingHours.length === 7) {
    const sunday = openingHours[6];
    openingHours = [sunday, ...openingHours.slice(0, 6)];
  }

  return {
    name: place.name,
    address: place.address || '',
    location: { latitude: lat, longitude: lng },
    rating: place.rating,
    reviewCount: place.reviewCount,
    distance: calculateDistance(searchLat, searchLng, lat, lng),
    openingHours: openingHours,
    googleMapsUrl: place.googleMapsUri ? `${place.googleMapsUri}?hl=he` : '',
    placeId: place.id,
    type: place.type
  };
}

// Create HTTP server
const server = http.createServer(async (req, res) => {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  // Health check
  if (path === '/health') {
    res.writeHead(200);
    res.end(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }));
    return;
  }

  // Adaptive search endpoint
  if (path === '/api/places/adaptive') {
    if (!checkRateLimit('local')) {
      res.writeHead(429);
      res.end(JSON.stringify({ success: false, error: 'RATE_LIMIT_EXCEEDED' }));
      return;
    }

    if (!apiKey) {
      res.writeHead(400);
      res.end(JSON.stringify({ success: false, error: 'API_KEY_NOT_SET', message: 'Please set your Google API key in settings' }));
      return;
    }

    try {
      const lat = parseFloat(url.searchParams.get('latitude'));
      const lng = parseFloat(url.searchParams.get('longitude'));
      const radius = parseFloat(url.searchParams.get('radius') || '15');
      const type = url.searchParams.get('type') || 'both';
      const minRating = parseFloat(url.searchParams.get('minRating') || '4.5');
      const minReviews = parseInt(url.searchParams.get('minReviews') || '100');

      if (isNaN(lat) || isNaN(lng)) {
        res.writeHead(400);
        res.end(JSON.stringify({ success: false, error: 'INVALID_COORDINATES' }));
        return;
      }

      const radiusMeters = radius * 1000;
      const typeGroups = type === 'restaurant' ? [['restaurant']] :
                         type === 'cafe' ? [['cafe', 'coffee_shop']] :
                         [['restaurant'], ['cafe', 'coffee_shop']];

      let allPlaces = [];
      let totalMetrics = { apiCalls: 0, uniquePlaces: 0 };

      for (const types of typeGroups) {
        const result = await adaptiveTilingSearch(lat, lng, radiusMeters, types);
        allPlaces.push(...result.places);
        totalMetrics.apiCalls += result.metrics.apiCalls;
      }

      // Deduplicate
      const seen = new Set();
      const unique = allPlaces.filter(p => {
        if (seen.has(p.id)) return false;
        seen.add(p.id);
        return true;
      });

      // Format and filter
      let formatted = unique.map(p => formatPlace(p, lat, lng));
      formatted = formatted.filter(p => p.rating >= minRating && p.reviewCount >= minReviews);
      formatted.sort((a, b) => b.rating - a.rating || b.reviewCount - a.reviewCount);

      res.writeHead(200);
      res.end(JSON.stringify({
        success: true,
        method: 'adaptive_tiling',
        location: { latitude: lat, longitude: lng },
        totalFound: unique.length,
        afterFilters: formatted.length,
        places: formatted,
        metrics: totalMetrics
      }));
    } catch (err) {
      console.error('Search error:', err);
      res.writeHead(500);
      res.end(JSON.stringify({ success: false, error: 'SEARCH_FAILED', message: err.message }));
    }
    return;
  }

  // 404
  res.writeHead(404);
  res.end(JSON.stringify({ success: false, error: 'NOT_FOUND' }));
});

// Start server
server.listen(PORT, '127.0.0.1', () => {
  console.log(`[Node.js] Server running on http://127.0.0.1:${PORT}`);
  channel.send('server-ready', { port: PORT });
});

// Listen for messages from Capacitor
channel.addListener('set-api-key', (key) => {
  apiKey = key;
  console.log('[Node.js] API key configured');
  channel.send('api-key-set', { success: true });
});

channel.addListener('ping', () => {
  channel.send('pong', { timestamp: Date.now() });
});

console.log('[Node.js] Starting embedded server...');
