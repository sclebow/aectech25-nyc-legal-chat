import { IfcViewerAPI } from 'web-ifc-viewer';
import * as THREE from 'three';

const urlParams = new URLSearchParams(window.location.search);
const ifcUrl = urlParams.get('ifcUrl') || '';

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
    console.log('Loading IFC from URL:', ifcUrl);
    try {
      const model = await viewer.IFC.loadIfcUrl(ifcUrl);
      console.log('IFC model loaded:', model);
      // --- Scale model to fixed bounds ---
      const desiredSize = 10; // Change this to your preferred bounding box size
      const box = new THREE.Box3().setFromObject(model.mesh);
      const size = new THREE.Vector3();
      box.getSize(size);
      const maxDim = Math.max(size.x, size.y, size.z);
      if (maxDim > 0) {
        const scale = desiredSize / maxDim;
        model.mesh.scale.set(scale, scale, scale);
      }
      // --- End scaling ---
      // Fit camera to model
      viewer.context.ifcCamera.cameraControls.fitToSphere(model.mesh);
      // Count meshes in the scene
      let meshCount = 0;
      viewer.context.getScene().traverse((obj) => {
        if (obj.isMesh) meshCount++;
      });
      console.log('Number of meshes in scene:', meshCount);
      if (!model || meshCount === 0) {
        container.innerHTML += '<h4>IFC loaded, but no geometry found or supported.</h4>';
      }
    } catch (err) {
      console.error('Error loading IFC:', err);
      container.innerHTML += `<h4 style='color:red;'>Error loading IFC: ${err.message}</h4>`;
    }
  } else {
    container.innerHTML = '<h3>No IFC file URL provided.</h3>';
  }
}

loadViewer();
