// KisanMind — Earth Engine Script for Crop Health Analysis
// Runs on project 'dmjone' (noncommercial, registered)
// Computes NDVI, EVI, NDWI from Sentinel-2 imagery

function analyzeCropHealth(lat, lon, days_back) {
  var point = ee.Geometry.Point([lon, lat]);
  var region = point.buffer(500); // 500m radius around point

  // Get Sentinel-2 Surface Reflectance imagery, cloud-masked
  var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(region)
    .filterDate(
      ee.Date(Date.now() - days_back * 86400000),
      ee.Date(Date.now())
    )
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
    .map(function(img) {
      // Cloud masking using SCL band
      var scl = img.select('SCL');
      var clear = scl.neq(3).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10));
      img = img.updateMask(clear);

      // Compute vegetation indices
      var ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI');
      var evi = img.expression(
        '2.5 * ((NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1))',
        {
          NIR: img.select('B8'),
          RED: img.select('B4'),
          BLUE: img.select('B2')
        }
      ).rename('EVI');
      var ndwi = img.normalizedDifference(['B3', 'B8']).rename('NDWI');

      return img.addBands([ndvi, evi, ndwi]);
    });

  // Check if we have any images
  var count = s2.size();

  // Latest composite
  var latest = s2.sort('system:time_start', false).first();

  // Mean NDVI for the region
  var ndvi_val = latest.select('NDVI').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: region,
    scale: 10
  });

  var evi_val = latest.select('EVI').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: region,
    scale: 10
  });

  var ndwi_val = latest.select('NDWI').reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: region,
    scale: 10
  });

  // Time series for trend analysis
  var ndvi_series = s2.select('NDVI').map(function(img) {
    var mean = img.reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: region,
      scale: 10
    });
    return ee.Feature(null, {
      'date': img.date().format('YYYY-MM-dd'),
      'ndvi': mean.get('NDVI')
    });
  });

  // False-color visualization (NIR-Red-Green) for Gemini analysis
  var falseColorVis = latest.select(['B8', 'B4', 'B3']).getThumbURL({
    region: region,
    dimensions: 512,
    min: 0,
    max: 3000,
    format: 'png'
  });

  // True-color visualization for dashboard
  var trueColorVis = latest.select(['B4', 'B3', 'B2']).getThumbURL({
    region: region,
    dimensions: 512,
    min: 0,
    max: 3000,
    format: 'png'
  });

  // NDVI visualization (red-yellow-green colormap)
  var ndviVis = latest.select('NDVI').getThumbURL({
    region: region,
    dimensions: 512,
    min: 0,
    max: 0.8,
    palette: ['red', 'orange', 'yellow', 'lightgreen', 'green', 'darkgreen'],
    format: 'png'
  });

  return {
    image_count: count,
    ndvi: ndvi_val,
    evi: evi_val,
    ndwi: ndwi_val,
    time_series: ndvi_series,
    false_color_url: falseColorVis,
    true_color_url: trueColorVis,
    ndvi_overlay_url: ndviVis,
    latest_date: latest.date().format('YYYY-MM-dd')
  };
}

// =============================================
// Demo: Analyze three locations
// =============================================

// Solan, Himachal Pradesh — Tomato farming
var solan = analyzeCropHealth(30.9045, 77.0967, 30);
print('Solan (Tomato):', solan);

// Coorg, Karnataka — Coffee plantations
var coorg = analyzeCropHealth(12.3375, 75.8069, 30);
print('Coorg (Coffee):', coorg);

// Ludhiana, Punjab — Wheat fields
var ludhiana = analyzeCropHealth(30.9010, 75.8573, 30);
print('Ludhiana (Wheat):', ludhiana);
