import { Client } from '@googlemaps/google-maps-services-js';
import { config } from './config.js';

// Initialize Google Maps Services client
export const googleMapsClient = new Client({});

// Export the API key for use in requests
export const apiKey = config.googlePlacesApiKey;
