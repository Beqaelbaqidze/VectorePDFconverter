from flask import Flask, render_template, request, jsonify
import pdfplumber
from shapely.geometry import LineString
import geopandas as gpd
import os
import math

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
EXPORT_FOLDER = 'exports'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXPORT_FOLDER'] = EXPORT_FOLDER

# Ensure the upload and export folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)

def is_finite_coordinate(coord):
    """Helper function to check if a coordinate is finite."""
    return all(math.isfinite(c) for c in coord)

def normalize_coordinates(x, y, page_width, page_height):
    """Normalize coordinates to a range of [0, 1] based on the PDF page dimensions."""
    norm_x = x / page_width
    norm_y = y / page_height
    return norm_x, norm_y

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract_shapes', methods=['POST'])
def extract_shapes():
    if 'pdf_file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['pdf_file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)
        
        all_shapes = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_width = page.width
                    page_height = page.height
                    lines = page.lines
                    for line in lines:
                        # Extract coordinates and normalize them
                        x0, y0 = normalize_coordinates(line['x0'], line['y0'], page_width, page_height)
                        x1, y1 = normalize_coordinates(line['x1'], line['y1'], page_width, page_height)
                        if is_finite_coordinate((x0, y0, x1, y1)):
                            shapely_line = LineString([(x0, y0), (x1, y1)])
                            if shapely_line.is_valid:
                                all_shapes.append(shapely_line)
                        else:
                            print(f"Invalid coordinates found: {x0}, {y0}, {x1}, {y1}")

            geo_shapes = [shape.__geo_interface__ for shape in all_shapes]
            return jsonify(geo_shapes)
        
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/export_shapefile', methods=['POST'])
def export_shapefile():
    try:
        shapes = request.json.get('shapes', [])
        shp_name = request.json.get('shp_name', 'exported_shapes')
        
        if not shapes:
            return jsonify({'error': 'No shapes provided'}), 400
        
        geometries = []
        for shape in shapes:
            if shape['type'] == 'LineString':
                coords = shape['coordinates']
                valid_coords = [coord for coord in coords if is_finite_coordinate(coord)]
                if valid_coords and len(valid_coords) > 1:
                    line = LineString(valid_coords)
                    if line.is_valid:
                        geometries.append(line)
                else:
                    print(f"Invalid or insufficient LineString found: {coords}")

        if not geometries:
            return jsonify({'error': 'No valid geometries to export'}), 400

        # Create a GeoDataFrame
        gdf = gpd.GeoDataFrame(geometry=geometries)

        # Save the GeoDataFrame to a Shapefile, which will create .shp, .shx, .dbf, and .prj files
        shp_path = os.path.join(app.config['EXPORT_FOLDER'], shp_name)
        gdf.to_file(f"{shp_path}.shp")

        return jsonify({'message': f'Shapefile {shp_name} saved successfully in the exports folder.'})
    
    except Exception as e:
        print(f"Error exporting shapefile: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
