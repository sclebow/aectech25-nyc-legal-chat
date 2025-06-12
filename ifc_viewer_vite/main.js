import { IfcViewerAPI } from 'web-ifc-viewer';

const urlParams = new URLSearchParams(window.location.search);
const ifcUrl = urlParams.get('ifc_url') || '';

async function loadViewer() {
  const container = document.getElementById('container');
  if (!container) return;
  // Use installed web-ifc-viewer
  const viewer = new IfcViewerAPI({
    container: container
    // backgroundColor: new Color(0.95, 0.95, 0.95)
  });
  viewer.grid.setGrid();
  viewer.axes.setAxes();
  viewer.IFC.setWasmPath('./node_modules/web-ifc-viewer/node_modules/web-ifc/');
  viewer.IFC.loader.ifcManager.applyWebIfcConfig({ "COORDINATE_TO_ORIGIN": true });
  if (ifcUrl) {
    viewer.IFC.loadIfcUrl(ifcUrl);
  } else {
    container.innerHTML = '<h3>No IFC file URL provided.</h3>';
  }
}

loadViewer();
