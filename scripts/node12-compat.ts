if (typeof Array.prototype.at !== "function") {
  Object.defineProperty(Array.prototype, "at", {
    configurable: true,
    writable: true,
    value<T>(this: T[], index: number): T | undefined {
      const normalized = Math.trunc(index);
      const position = normalized < 0 ? this.length + normalized : normalized;
      return position >= 0 && position < this.length
        ? this[position]
        : undefined;
    },
  });
}

if (typeof Object.hasOwn !== "function") {
  Object.defineProperty(Object, "hasOwn", {
    configurable: true,
    writable: true,
    value(target: object, key: PropertyKey): boolean {
      return Object.prototype.hasOwnProperty.call(target, key);
    },
  });
}
