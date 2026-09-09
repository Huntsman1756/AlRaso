# Registro de desviaciones del protocolo M7

Estado inicial:

```text
NO_DEVIATIONS_AS_OF_PROTOCOL_CANDIDATE
```

Al congelarse el protocolo, esta línea debe actualizarse a:

```text
NO_DEVIATIONS_AS_OF_FREEZE
```

## Formato de registro de desviación

Cada desviación posterior registra, sin excepción:

- `date`: fecha
- `proposed_by`: quién propone
- `description`: qué cambia
- `reason`: por qué
- `results_already_visible`: si los resultados ya eran visibles cuando se propuso (sí/no)
- `expected_effect`: efecto esperado sobre validez/sesgo
- `disposition`: aceptada / rechazada / escalada a NEEDS_HUMAN_DECISION

Regla: NO se modifica la metodología silenciosamente después de ver resultados. Toda modificación del marco, del main set, del paquete del revisor, de la matriz de desacuerdo o de la puerta de freeze pasa por aquí.

## Desviaciones

(ninguna)
