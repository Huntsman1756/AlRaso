# Seguridad

---

## Versión soportada

Únicamente la rama `main`. AlRaso es **software alpha de investigación**; no hay versiones estables ni LTS. Las vulnerabilidades se corrigen en `main`.

## Cómo reportar un problema

Usa **GitHub Security Advisories** (privado) → [Reporting Security Issues](https://docs.github.com/es/code-security/security-advisories/guidance-on-reporting-and-editing/about-security-advisories).

> **No abras un issue público.** Los issues públicos son para funcionalidad, documentación y trabajo visible.

## Alcance

- **Sin telemetría.** AlRaso no recolecta, envía ni almacena datos de uso.
- **Sin backend remoto/SaaS.** El servidor corre como stdlib local (python, sin dependencias);
  la persistencia se limita a `localStorage`.
- **Sin asesoramiento jurídico.** El software determina regímenes normativos codificados en el corpus; no cubre restricciones operativas (reservas, accesos, avisos).
- **Datos de terceros.** Tiles (OpenFreeMap), POIs (OSM/Overpass) y documentos oficiales se rigen por sus propias licencias y términos (ver `NOTICE.md`).