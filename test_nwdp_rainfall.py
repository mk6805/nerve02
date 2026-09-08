import rasterio
import numpy as np
import matplotlib.pyplot as plt


files = {
    "Elevation": "N26E091_DEM.tif",
    "Slope": "N26E091_slope.tif",
    "Aspect": "N26E091_aspect.tif",
    "Flow Direction": "N26E091_flow_direction.tif",
    "Flow Accumulation": "N26E091_flow_accumulation.tif"
}


for name, filename in files.items():

    print(f"\nChecking {name}...")

    with rasterio.open(filename) as src:

        data = src.read(1)

        print("  CRS:", src.crs)
        print("  Shape:", data.shape)
        print("  Resolution:", src.res)
        print("  Bounds:", src.bounds)
        print("  Minimum:", float(np.nanmin(data)))
        print("  Maximum:", float(np.nanmax(data)))

        # Flow accumulation has a very large range,
        # so logarithmic scaling makes drainage patterns visible.
        if name == "Flow Accumulation":
            display_data = np.log1p(np.maximum(data, 0))
        else:
            display_data = data

        plt.figure(figsize=(10, 8))

        plt.imshow(
            display_data,
            extent=[
                src.bounds.left,
                src.bounds.right,
                src.bounds.bottom,
                src.bounds.top
            ],
            origin="upper"
        )

        plt.title(name)
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.colorbar(label=name)

        output_name = filename.replace(".tif", ".png")
        plt.savefig(output_name, dpi=150, bbox_inches="tight")
        plt.close()

        print("  Saved:", output_name)


print("\nAll terrain layers visualized successfully!")