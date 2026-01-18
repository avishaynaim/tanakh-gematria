import { googleMapsClient, apiKey } from './placesClient.js';

/**
 * Validates coordinate ranges
 * @param {number} latitude - Latitude value
 * @param {number} longitude - Longitude value
 * @returns {boolean} - True if valid, false otherwise
 */
export function validateCoordinates(latitude, longitude) {
  const lat = parseFloat(latitude);
  const lng = parseFloat(longitude);

  if (isNaN(lat) || isNaN(lng)) {
    return false;
  }

  return lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

/**
 * Geocodes a city name to coordinates using Google Geocoding API
 * @param {string} cityName - Name of the city
 * @returns {Promise<{latitude: number, longitude: number, formattedAddress: string}>}
 * @throws {Error} - If geocoding fails
 */
export async function geocodeCity(cityName) {
  try {
    const response = await googleMapsClient.geocode({
      params: {
        address: cityName,
        language: 'he',
        key: apiKey,
      },
    });

    if (response.data.status === 'OK' && response.data.results.length > 0) {
      const result = response.data.results[0];
      return {
        latitude: result.geometry.location.lat,
        longitude: result.geometry.location.lng,
        formattedAddress: result.formatted_address,
      };
    } else if (response.data.status === 'ZERO_RESULTS') {
      throw new Error(`City not found: ${cityName}`);
    } else {
      throw new Error(`Geocoding failed: ${response.data.status}`);
    }
  } catch (error) {
    if (error.message.includes('City not found') || error.message.includes('Geocoding failed')) {
      throw error;
    }
    throw new Error(`Geocoding error: ${error.message}`);
  }
}

/**
 * Processes location input with precedence logic
 * @param {Object} params - Location parameters
 * @param {string} params.city - City name (optional)
 * @param {number} params.latitude - Latitude coordinate (optional)
 * @param {number} params.longitude - Longitude coordinate (optional)
 * @returns {Promise<{latitude: number, longitude: number, formattedAddress: string}>}
 * @throws {Error} - If location validation fails
 */
export async function processLocation({ city, latitude, longitude }) {
  // Check if coordinates are provided
  const hasCoordinates = latitude !== undefined && longitude !== undefined;
  const hasCity = city && city.trim().length > 0;

  // Validation: at least one input method required
  if (!hasCoordinates && !hasCity) {
    throw new Error('Either city name or coordinates must be provided');
  }

  // Precedence: coordinates override city name
  if (hasCoordinates) {
    // Validate coordinate ranges
    if (!validateCoordinates(latitude, longitude)) {
      throw new Error('Invalid coordinates. Latitude must be between -90 and 90, longitude must be between -180 and 180');
    }

    return {
      latitude: parseFloat(latitude),
      longitude: parseFloat(longitude),
      formattedAddress: `${latitude}, ${longitude}`,
    };
  }

  // If only city name provided, geocode it
  if (hasCity) {
    return await geocodeCity(city);
  }
}
