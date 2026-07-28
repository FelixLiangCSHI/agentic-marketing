const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const TIME_PATTERN = /^(?:[01]\d|2[0-3]):[0-5]\d$/;

interface DateTimeParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
}

export function isValidIsoDate(value: string): boolean {
  if (!ISO_DATE_PATTERN.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return (
    !Number.isNaN(parsed.valueOf()) &&
    parsed.toISOString().slice(0, 10) === value
  );
}

export function isValidTime(value: string): boolean {
  return TIME_PATTERN.test(value);
}

export function addDays(date: string, days: number): string {
  if (!isValidIsoDate(date)) {
    throw new Error(`Invalid ISO date: ${date}`);
  }
  const parsed = new Date(`${date}T00:00:00.000Z`);
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

export function isValidIanaTimeZone(timeZone: string): boolean {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone }).format(new Date(0));
    return true;
  } catch {
    return false;
  }
}

function dateTimePartsInZone(
  instant: Date,
  timeZone: string,
): DateTimeParts | null {
  try {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).formatToParts(instant);
    const values = Object.fromEntries(
      parts
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, Number(part.value)]),
    );
    if (
      !Number.isInteger(values.year) ||
      !Number.isInteger(values.month) ||
      !Number.isInteger(values.day) ||
      !Number.isInteger(values.hour) ||
      !Number.isInteger(values.minute)
    ) {
      return null;
    }
    return {
      year: values.year,
      month: values.month,
      day: values.day,
      hour: values.hour,
      minute: values.minute,
    };
  } catch {
    return null;
  }
}

export function localDateInTimeZone(
  now: Date,
  timeZone: string,
): string | null {
  const parts = dateTimePartsInZone(now, timeZone);
  if (!parts) {
    return null;
  }
  return [
    String(parts.year).padStart(4, "0"),
    String(parts.month).padStart(2, "0"),
    String(parts.day).padStart(2, "0"),
  ].join("-");
}

function offsetMilliseconds(instant: Date, timeZone: string): number | null {
  const parts = dateTimePartsInZone(instant, timeZone);
  if (!parts) {
    return null;
  }
  const representedAsUtc = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
  );
  return representedAsUtc - Math.floor(instant.valueOf() / 60_000) * 60_000;
}

export function zonedDateTimeToUtc(
  date: string,
  time: string,
  timeZone: string,
): Date | null {
  if (
    !isValidIsoDate(date) ||
    !isValidTime(time) ||
    !isValidIanaTimeZone(timeZone)
  ) {
    return null;
  }

  const [year, month, day] = date.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  const wallClockAsUtc = Date.UTC(year, month - 1, day, hour, minute);
  const firstOffset = offsetMilliseconds(new Date(wallClockAsUtc), timeZone);
  if (firstOffset === null) {
    return null;
  }
  let candidate = new Date(wallClockAsUtc - firstOffset);
  const correctedOffset = offsetMilliseconds(candidate, timeZone);
  if (correctedOffset === null) {
    return null;
  }
  candidate = new Date(wallClockAsUtc - correctedOffset);

  const represented = dateTimePartsInZone(candidate, timeZone);
  if (
    !represented ||
    represented.year !== year ||
    represented.month !== month ||
    represented.day !== day ||
    represented.hour !== hour ||
    represented.minute !== minute
  ) {
    return null;
  }
  return candidate;
}
