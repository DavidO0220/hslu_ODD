"""IDS-Import: Prüfregeln aus einer IDS-Datei (buildingSMART) lesen.

IDS (Information Delivery Specification) beschreibt maschinenlesbar, welche
Informationen ein Modell enthalten muss, zum Beispiel «alle IfcWall brauchen
Pset_WallCommon.FireRating mit einem Wert aus EI30, EI60, EI90».

Dieses Modul übersetzt die Teile einer IDS, die zum IFC-Property-Editor passen,
in dasselbe Regelformat wie config/rules.json. Der Validator prüft danach
Eingaben und das Modell wie gewohnt.

Übernommen werden:
- Anwendbarkeit über die Bauteilklasse (Facet «entity», ein Wert oder eine Liste)
- Anforderungen an Properties (Facet «property») mit festem Pset- und Property-Namen:
  fester Wert, Werteliste, Muster (Regex), Zahlenbereich, Datentyp, Pflicht/optional/verboten

Nicht übernommen und im Bericht aufgeführt:
- andere Facets (Attribut, Klassifikation, Material, partOf) als Anwendbarkeit oder Anforderung
- Pset- oder Property-Namen als Muster, Längenbeschränkungen, PredefinedType

Grenze: IDS gibt Zahlen in SI-Einheiten an (Länge in m). Eine Umrechnung für
Modelle in anderen Einheiten (z. B. mm) gibt es nicht.
"""

import xml.etree.ElementTree as ET

IDS_NS = "http://standards.buildingsmart.org/IDS"
XS_NS = "http://www.w3.org/2001/XMLSchema"
_I = "{%s}" % IDS_NS
_X = "{%s}" % XS_NS

TEXT_TYPES = {"IFCLABEL", "IFCTEXT", "IFCIDENTIFIER"}
BOOL_TYPES = {"IFCBOOLEAN", "IFCLOGICAL"}
NUMBER_TYPES = {"IFCREAL", "IFCINTEGER", "IFCNUMERICMEASURE", "IFCCOUNTMEASURE"}


class IdsError(ValueError):
    """Die Datei ist keine lesbare IDS."""


def _is_number_type(data_type: str | None) -> bool:
    return bool(data_type) and (data_type in NUMBER_TYPES or data_type.endswith("MEASURE"))


def _value(node):
    """Inhalt eines idsValue: ("simple", Text) oder ("restriction", {...}) oder None."""
    if node is None:
        return None
    simple = node.find(_I + "simpleValue")
    if simple is not None:
        return "simple", (simple.text or "").strip()
    restriction = node.find(_X + "restriction")
    if restriction is None:
        return None
    parts = {"enumeration": [], "pattern": [], "other": []}
    for child in restriction:
        tag = child.tag.replace(_X, "")
        value = child.get("value")
        if tag in ("enumeration", "pattern"):
            parts[tag].append(value)
        elif tag in ("minInclusive", "maxInclusive", "minExclusive", "maxExclusive"):
            parts[tag] = float(value)
        else:
            parts["other"].append(tag)
    return "restriction", parts


def _names(node) -> list[str] | None:
    """Fester Name oder Liste von Namen, sonst None (z. B. Muster)."""
    v = _value(node)
    if v is None:
        return None
    kind, content = v
    if kind == "simple":
        return [content] if content else None
    if content["enumeration"] and not content["pattern"]:
        return content["enumeration"]
    return None


def _rule(prop, spec_name: str, notes: list[str]) -> dict | None:
    """Eine Property-Anforderung als Regel im Format von rules.json."""
    data_type = (prop.get("dataType") or "").upper() or None
    cardinality = prop.get("cardinality", "required")
    if cardinality == "prohibited":
        return {"type": "prohibited", "source": spec_name}

    rule: dict = {}
    v = _value(prop.find(_I + "value"))
    if v is None:
        if data_type in BOOL_TYPES:
            rule = {"type": "bool"}
        elif _is_number_type(data_type):
            rule = {"type": "float"}
        else:
            rule = {"type": "text"}
    elif v[0] == "simple":
        text = v[1]
        if data_type in BOOL_TYPES:
            rule = {"type": "bool", "value": text.upper() == "TRUE"}
        elif _is_number_type(data_type):
            rule = {"type": "float", "min": float(text), "max": float(text)}
        else:
            rule = {"type": "enum", "values": [text]}
    else:
        parts = v[1]
        if parts["other"]:
            notes.append(f"«{spec_name}»: Einschränkung {', '.join(parts['other'])} wird nicht geprüft.")
        if parts["enumeration"]:
            rule = {"type": "enum", "values": parts["enumeration"]}
        elif parts["pattern"]:
            patterns = parts["pattern"]
            rule = {"type": "pattern",
                    "pattern": patterns[0] if len(patterns) == 1 else "|".join(f"(?:{p})" for p in patterns)}
        elif any(k in parts for k in ("minInclusive", "maxInclusive", "minExclusive", "maxExclusive")):
            rule = {"type": "float"}
            for k, target in (("minInclusive", "min"), ("maxInclusive", "max"),
                              ("minExclusive", "min_exclusive"), ("maxExclusive", "max_exclusive")):
                if k in parts:
                    rule[target] = parts[k]
        else:
            rule = {"type": "text"}
    rule["required"] = cardinality == "required"
    if data_type:
        rule["dataType"] = data_type
    if prop.get("instructions"):
        rule["instructions"] = prop.get("instructions")
    rule["source"] = spec_name
    return rule


def parse_ids(data: bytes) -> tuple[dict, list[str], dict]:
    """Liest eine IDS-Datei.

    Rückgabe: (Regeln im Format von rules.json, Hinweise zu nicht Übernommenem,
    Info {"title", "specifications", "rules", "ifc_versions"}).
    Klassennamen stehen so in den Regeln, wie die IDS sie schreibt (meist IFCWALL);
    validator.rules_for_class vergleicht ohne Gross-/Kleinschreibung.
    """
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise IdsError(f"Die Datei ist kein gültiges XML: {exc}") from exc
    if root.tag != _I + "ids":
        raise IdsError("Die Datei ist keine IDS-Datei (Element «ids» im Namensraum von buildingSMART fehlt).")

    title_node = root.find(f"{_I}info/{_I}title")
    rules: dict = {}
    notes: list[str] = []
    versions: set[str] = set()
    specs = root.findall(f"{_I}specifications/{_I}specification")
    count = 0
    for spec in specs:
        name = spec.get("name") or "ohne Namen"
        versions.update((spec.get("ifcVersion") or "").split())
        applicability = spec.find(_I + "applicability")
        facets = [c for c in (applicability if applicability is not None else [])]
        entities = [f for f in facets if f.tag == _I + "entity"]
        others = [f.tag.replace(_I, "") for f in facets if f.tag != _I + "entity"]
        if others or len(entities) != 1:
            why = f"Anwendbarkeit über {', '.join(others)}" if others else "Anwendbarkeit ohne genau eine Bauteilklasse"
            notes.append(f"«{name}» nicht übernommen: {why} wird nicht unterstützt.")
            continue
        classes = _names(entities[0].find(_I + "name"))
        if not classes:
            notes.append(f"«{name}» nicht übernommen: Bauteilklasse als Muster wird nicht unterstützt.")
            continue
        if entities[0].find(_I + "predefinedType") is not None:
            notes.append(f"«{name}»: PredefinedType wird ignoriert, die Regeln gelten für die ganze Klasse.")

        requirements = spec.find(_I + "requirements")
        for req in (requirements if requirements is not None else []):
            tag = req.tag.replace(_I, "")
            if tag != "property":
                notes.append(f"«{name}»: Anforderung «{tag}» wird nicht geprüft.")
                continue
            psets = _names(req.find(_I + "propertySet"))
            props = _names(req.find(_I + "baseName"))
            if not psets or not props or len(psets) != 1:
                notes.append(f"«{name}»: Property mit Muster im Pset- oder Property-Namen wird nicht geprüft.")
                continue
            rule = _rule(req, name, notes)
            for cls in classes:
                for prop_name in props:
                    target = rules.setdefault(cls.strip(), {}).setdefault(psets[0], {})
                    if prop_name in target:
                        notes.append(f"«{name}»: {cls} {psets[0]}.{prop_name} kommt mehrfach vor, die letzte Regel gilt.")
                    target[prop_name] = dict(rule)
                    count += 1
    info = {"title": (title_node.text or "").strip() if title_node is not None else "",
            "specifications": len(specs), "rules": count, "ifc_versions": sorted(versions)}
    return rules, notes, info
