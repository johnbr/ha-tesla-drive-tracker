/** Text for the info panel. Import-free. */

export type DistanceUnit = "mi" | "km";

const KM_PER_MILE = 1.609344;

export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const rest = minutes % 60;
  return rest ? `${Math.floor(minutes / 60)} h ${rest} min` : `${minutes / 60} h`;
}

export function formatDistance(miles: number, unit: DistanceUnit): string {
  const value = unit === "km" ? miles * KM_PER_MILE : miles;
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${unit}`;
}

export function formatSpeed(mph: number, unit: DistanceUnit): string {
  return unit === "km" ? `${Math.round(mph * KM_PER_MILE)} km/h` : `${Math.round(mph)} mph`;
}

export function formatAge(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} s`;
  return `${Math.round(seconds / 60)} min`;
}

export function formatTime(epochSeconds: number, locale: string, hour12: boolean | undefined): string {
  const hour = hour12 === false ? "2-digit" : "numeric";
  return new Intl.DateTimeFormat(locale, { hour, minute: "2-digit", hour12 }).format(new Date(epochSeconds * 1000));
}

export function unitFor(configured: string, haLength: string | undefined): DistanceUnit {
  if (configured === "mi" || configured === "km") return configured;
  return haLength === "km" ? "km" : "mi";
}
