import re
from dataclasses import dataclass
from pathlib import Path
from pm4py.objects.ocel.importer.jsonocel import importer as jsonocel_importer
from pm4py.algo.discovery.ocel.ocdfg import algorithm as ocdfg_discovery
from pm4py.visualization.ocel.ocdfg import visualizer as ocdfg_visualizer
from pm4py.algo.discovery.ocel.ocpn import algorithm as ocpn_discovery
from pm4py.visualization.ocel.ocpn import visualizer as ocpn_visualizer
from pm4py.visualization.ocel.eve_to_obj_types import visualizer as eto_visualizer


def force_bw(gviz):
    """Rewrite all color attributes to black/white based on actual body format."""
    new_body = []
    for line in gviz.body:
        # Replace all hex color values for color/fillcolor/fontcolor
        line = re.sub(r'\b(color)="#[0-9a-fA-F]+"', r"\1=black", line)
        line = re.sub(r'\b(fillcolor)="#[0-9a-fA-F]+"', r"\1=white", line)
        line = re.sub(r'\b(fontcolor)="#[0-9a-fA-F]+"', r"\1=black", line)

        if "style=filled" in line and 'label=" "' in line:
            line = re.sub(r"\bfillcolor=white\b", "fillcolor=black", line)

        new_body.append(line)

    gviz.body = new_body
    return gviz


def force_translucent_nodes(gviz, alpha_hex="E6"):
    """Use alpha_hex values to set node translucency. Values range from 00 (fully transparent) to FF (fully opaque):
    0% = 00
    10% = 1A
    20% = 33
    30% = 4D
    40% = 66
    50% = 80
    60% = 99
    70% = B3
    80% = CC
    90% = E6
    100% = FF"""

    new_body = []
    for line in gviz.body:
        line = re.sub(
            r'(\bfillcolor=)"#([0-9a-fA-F]{6})"',
            lambda m: f'{m.group(1)}"# {m.group(2)}{alpha_hex}"',
            line,
        )
        line = re.sub(
            r'(\bfontcolor=)"#([0-9a-fA-F]{6})"',
            r"\1black",
            line,
        )
        new_body.append(line)

    gviz.body = new_body
    return gviz


@dataclass
class VisualizationConfig:
    ocel_path: Path
    out_dir: Path
    export_format: str = "svg"
    ocel_variant = jsonocel_importer.Variants.OCEL20_STANDARD


class Visualizer:
    def __init__(self, config: VisualizationConfig):
        self.config = config
        self.config.out_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> dict[str, Path]:
        """Run all visualizations and return a dictionary of output paths."""
        ocel = self._load_ocel()

        outputs = {}
        outputs["object_types"] = self._export_object_types(ocel)
        outputs["oc_dfg"] = self._export_ocdfg(ocel)
        outputs["oc_pn"] = self._export_ocpn(ocel)

        return outputs

    def _load_ocel(self):
        """Load the OCEL file in json format."""
        return jsonocel_importer.apply(
            str(self.config.ocel_path),
            variant=self.config.ocel_variant,
        )

    def _export_object_types(self, ocel) -> Path:
        """Export an object types visualization."""
        gviz = eto_visualizer.apply(
            ocel, parameters={"format": self.config.export_format}
        )
        target = self.config.out_dir / f"object-types.{self.config.export_format}"
        eto_visualizer.save(gviz, str(target))
        return target

    def _export_ocdfg(self, ocel) -> Path:
        """Expot an object centric directly-follows graph visualization."""
        ocdfg = ocdfg_discovery.apply(ocel)
        gviz = force_translucent_nodes(
            ocdfg_visualizer.apply(
                ocdfg, parameters={"format": self.config.export_format}
            ),
            "CC",
        )
        target = self.config.out_dir / f"oc-dfg.{self.config.export_format}"
        ocdfg_visualizer.save(gviz, str(target))
        return target

    def _export_ocpn(self, ocel) -> Path:
        """Export an object centric Petri net visualization."""
        ocpn = ocpn_discovery.apply(ocel)
        gviz = force_translucent_nodes(
            ocpn_visualizer.apply(
                ocpn, parameters={"format": self.config.export_format}
            ),
            "80",
        )
        target = self.config.out_dir / f"oc-pn.{self.config.export_format}"
        ocpn_visualizer.save(gviz, str(target))
        return target


# Example usage:
if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parents[2]
    config = VisualizationConfig(
        ocel_path=root_dir / "event_logs" / "demo_1.json",
        out_dir=root_dir / "generated_visualizations",
        export_format="svg",
    )
    visualizer = Visualizer(config)
    result = visualizer.run()
    print("Generated:", result)
