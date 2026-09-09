# Instrucciones para el revisor jurídico independiente M7 (v1)

## Qué es este trabajo

Revisión jurídica independiente, a ciegas, de 28 casos concretos de vivac/pernocta al raso en el Parque Nacional de los Picos de Europa (24 del main set + 4 del holdout). Usted responderá cada caso por su cuenta, con fuentes primarias oficiales, SIN conocer ninguna determinación previa del sistema evaluado.

- Esfuerzo estimado: **6–10 horas cualificadas** (estimación de planificación; usted decide si la acepta).
- La identidad y la cualificación del revisor se verifican en privado antes del inicio. El informe público describirá la experiencia relevante y el ámbito, sin publicar datos personales innecesarios.

## Qué recibirá

Para cada caso:

- coordenadas (cuando existan) o localización factual declarada;
- actividad declarada;
- `activity_date`;
- hechos conocidos (noches, cota si existe, tamaño de grupo, contexto declarado);
- una pregunta jurídica neutral;
- referencias a fuentes primarias oficiales: BOCyL, BOPA, BOC, BOE, y evidencia espacial oficial necesaria (IGN/CNIG BDDAE/INSPIRE para límites autonómicos, OAPN para el límite del parque, IGN/CNIG MDT25 para elevaciones).

Los PDFs de los diarios oficiales NO se redistribuyen: usted los obtiene en los portales oficiales citados (BOCyL, BOPA, BOC, BOE).

## Qué NO recibirá (ceguera)

Usted NO recibirá, y no debe consultar:

- fixtures de reglas legales codificadas del sistema evaluado;
- resultados esperados, aserciones de tests o trazas del motor;
- la determinación actual de ningún caso según ese sistema;
- notas de interpretación interna.

Usted NO debe navegar el repositorio del proyecto durante la revisión. Si algún material de descubrimiento secundario (p. ej., textos consolidados no oficiales) le resulta útil como lectura, úselo solo como ayuda de descubrimiento, etiquételo como tal en su respuesta y delegue la autoridad en la fuente primaria oficial.

## Qué debe devolver por caso

1. `status`: uno de
   - `PERMITTED`
   - `PROHIBITED`
   - `AUTHORIZATION_REQUIRED`
   - `UNDETERMINED_LEGAL` (las fuentes no sostienen una conclusión suficientemente fuerte)
   - `UNDETERMINED_FACTUAL` (la regla puede estar clara, pero falta un hecho requerido o es inverificable)
   - `OUT_OF_SCOPE` (el caso queda fuera del ámbito de la norma invocada)
2. `provision`: precepto exacto (diario oficial, decreto, artículo y apartado).
3. `applicable_wording`: cita literal del texto oficial aplicable.
4. `validity_reasoning`: por qué ese precepto es válido y aplicable en `activity_date`.
5. `interpretation_rationale`: razonamiento interpretativo breve.

Una respuesta tipo "creo que está permitido" NO es una conclusión jurídica fuerte: sin precepto exacto + redacción aplicable + vigencia + razonamiento, el caso debe devolverse como `UNDETERMINED_LEGAL`.

Notas:

- Si la regla es clara pero el caso no aporta un hecho requerido (cota, nº de noches, posición, jurisdicción), use `UNDETERMINED_FACTUAL` e identifique EL HECHO que falta.
- Los materiales consolidados/foros/guías nunca sustituyen al diario oficial.
- Puede declarar `OUT_OF_SCOPE` cuando los hechos no queden gobernados por la norma invocada.

## Sellado y derecho de anotación

- Sus respuestas se reciben, se sellan y quedan inmutables ANTES de que se revelen los resultados del sistema evaluado.
- Después del sellado, el autor del proyecto redactará una adjudicación por desacuerdo; usted recibirá ese borrador y tendrá derecho de anotación: `AGREE`, `DISAGREE` o `QUALIFY`, con un comentario breve.
- Su anotación se publica intacta: nadie la sobrescribirá ni reformulará.

## Confidencialidad

- Durante la revisión, no consulte con el autor del proyecto ni con nadie implicado en él.
- El contenido de los casos es de uso exclusivo de esta revisión hasta la publicación del informe.
