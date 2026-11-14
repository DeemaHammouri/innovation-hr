"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Errors<T> = Partial<Record<keyof T, string>>;

/**
 * Forms that validate on blur, clear an error as soon as the person comes back to the field,
 * and never disable the submit button. Submitting with problems jumps to the first one.
 */
export function useForm<T extends Record<string, string>>(initial: T, validate: (values: T) => Errors<T>) {
  const [values, setValues] = useState<T>(initial);
  const [errors, setErrors] = useState<Errors<T>>({});
  const valuesRef = useRef(values);
  const focusingProgrammatically = useRef(false);
  useEffect(() => {
    valuesRef.current = values;
  }, [values]);

  const clear = useCallback((name: keyof T) => {
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const field = (name: keyof T & string) => ({
    name,
    value: values[name],
    error: errors[name],
    onChange: (e: { target: { value: string } }) => {
      const value = e.target.value;
      setValues((prev) => ({ ...prev, [name]: value }));
      clear(name);
    },
    onFocus: () => {
      if (!focusingProgrammatically.current) clear(name);
    },
    onBlur: () => {
      const message = validate(valuesRef.current)[name];
      if (message) setErrors((prev) => ({ ...prev, [name]: message }));
    },
  });

  const setValue = (name: keyof T, value: string) => {
    setValues((prev) => ({ ...prev, [name]: value }));
    clear(name);
  };

  /** Moves focus to a field and keeps its error visible (a person arriving by themselves clears it). */
  const focusField = (name: string) => {
    focusingProgrammatically.current = true;
    document.getElementById(`field-${name}`)?.focus();
    focusingProgrammatically.current = false;
  };

  /** Runs every rule. Returns true when the form is fine; otherwise shows the errors and focuses the first. */
  const check = () => {
    const found = validate(values);
    setErrors(found);
    const first = (Object.keys(initial) as (keyof T & string)[]).find((k) => found[k]);
    if (first) focusField(first);
    return !first;
  };

  return { values, errors, field, setValue, setErrors, check, focusField };
}

export const isEmail = (value: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
