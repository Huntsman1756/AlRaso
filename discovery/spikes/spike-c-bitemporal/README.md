# Spike C — Bitemporalidad (desechable)

Hipótesis: valid time + system time permiten responder "¿qué sabíamos?" y "¿qué era aplicable?" de forma independiente, y detectar determinaciones obsoletas.

## Ejecutar
```bash
python spike-c-bitemporal.py
```

## Resultado (verificado)
```text
resolve(activity=2023-06-15, knowledge=2023-06-15) -> PERMITTED   (correcto-conocimiento-de-entonces)
descubrimiento tardío 2027 (D 16/2022 prohibía desde 2022-02-09; append-only)
resolve(activity=2023-06-15, knowledge=2028-01-01) -> PROHIBITED  (hoy)
sistema vigilante (recorded 2022) habría respondido PROHIBITED
retro-auditoría: answered then=PERMITTED | in force=PROHIBITED -> flag STALE
```

## Hallazgos clave
1. El cierre de `effective_to` retroactivo debe ser append-only (fila nueva con `recorded_at` del cierre).
2. Intersección vacía (versión expirada + sucesor desconocido a esa knowledge date) → `UNDETERMINED` + knowledge INCOMPLETE, no silencio.
3. Axiom NO puede hacer esto hoy (assessment_date ignorado) → esta capa es nuestra.
