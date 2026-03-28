"use client";

import { useState, useEffect, useCallback } from "react";

interface GeolocationState {
  latitude: number | null;
  longitude: number | null;
  accuracy: number | null;
  loading: boolean;
  error: string | null;
}

export default function useGeolocation() {
  const [state, setState] = useState<GeolocationState>({
    latitude: null,
    longitude: null,
    accuracy: null,
    loading: true,
    error: null,
  });

  const requestLocation = useCallback(() => {
    setState((prev) => ({ ...prev, loading: true, error: null }));

    if (!navigator.geolocation) {
      // Fall back to IP-based geolocation
      fetchIPLocation();
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setState({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          loading: false,
          error: null,
        });
      },
      () => {
        // GPS denied or failed — fall back to IP-based
        fetchIPLocation();
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  }, []);

  async function fetchIPLocation() {
    try {
      const res = await fetch("https://ipapi.co/json/", { signal: AbortSignal.timeout(5000) });
      if (!res.ok) throw new Error("IP lookup failed");
      const data = await res.json();
      setState({
        latitude: data.latitude ?? 28.6139,
        longitude: data.longitude ?? 77.209,
        accuracy: 50000, // IP-based, ~50km accuracy
        loading: false,
        error: null,
      });
    } catch {
      // Absolute fallback: center of India
      setState({
        latitude: 22.9734,
        longitude: 78.6569,
        accuracy: 500000,
        loading: false,
        error: "Could not determine location. Using default.",
      });
    }
  }

  useEffect(() => {
    requestLocation();
  }, [requestLocation]);

  return { ...state, refresh: requestLocation };
}
