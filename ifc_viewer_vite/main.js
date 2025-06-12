import { IfcViewerAPI } from 'web-ifc-viewer';
import * as THREE from 'three';

const urlParams = new URLSearchParams(window.location.search);
const ifcUrl = urlParams.get('ifcUrl') || '';

async function loadViewer() {
  const container = document.getElementById('container');
  if (!container) return;
  // Make container responsive
  container.style.width = '100vw';
  container.style.height = '100vh';
  container.style.position = 'fixed';
  container.style.top = '0';
  container.style.left = '0';
  container.style.margin = '0';
  container.style.padding = '0';
  // Use installed web-ifc-viewer with antialiasing and background color
  const viewer = new IfcViewerAPI({
    container: container,
    backgroundColor: new THREE.Color(0.95, 0.96, 0.98), // Soft neutral
    rendererOptions: { antialias: true }
  });
  // Enable shadows if supported
  if (viewer.context && viewer.context.renderer && viewer.context.renderer.shadowMap) {
    viewer.context.renderer.shadowMap.enabled = true;
    viewer.context.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }
  viewer.grid.setGrid();
  viewer.axes.setAxes();
  viewer.IFC.setWasmPath('./node_modules/web-ifc-viewer/node_modules/web-ifc/');
  viewer.IFC.loader.ifcManager.applyWebIfcConfig({ "COORDINATE_TO_ORIGIN": true });
  if (ifcUrl) {
    console.log('Loading IFC from URL:', ifcUrl);
    try {
      const model = await viewer.IFC.loadIfcUrl(ifcUrl);
      // --- Apply physically-based or semi-transparent material ---
      model.mesh.traverse((child) => {
        if (child.isMesh) {
          child.material = new THREE.MeshPhysicalMaterial({
            color: 0xffffff,
            metalness: 0.1,
            roughness: 0.6,
            opacity: 0.85,
            transparent: true,
            transmission: 0.2,
            clearcoat: 0.1
          });
          child.castShadow = true;
          child.receiveShadow = true;
        }
      });
      // --- End material ---
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
      // Center model at origin (recompute box after scaling)
      const boxScaled = new THREE.Box3().setFromObject(model.mesh);
      const center = new THREE.Vector3();
      boxScaled.getCenter(center);
      // Only move on horizontals, move bottom of model to 0
      model.mesh.position.x -= center.x;
      model.mesh.position.y = -boxScaled.min.y; // Move bottom to y=0
      model.mesh.position.z -= center.z; // Move bottom to z=0
      // --- End centering ---
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
      // --- Add outline edges to all meshes (not full wireframe) ---
      model.mesh.traverse((child) => {
        if (child.isMesh) {
          const edges = new THREE.EdgesGeometry(child.geometry, 1); // 1 is the threshold angle in radians
          const outline = new THREE.LineSegments(
            edges,
            new THREE.LineBasicMaterial({ color: 0x000000, linewidth: 1 })
          );
          outline.renderOrder = 1; // Ensure outline renders on top
          child.add(outline);
        }
      });
      // --- End outline edges ---
    } catch (err) {
      console.error('Error loading IFC:', err);
      container.innerHTML += `<h4 style='color:red;'>Error loading IFC: ${err.message}</h4>`;
    }
  } else {
    container.innerHTML = '<h3>No IFC file URL provided.</h3>';
  }

  // Responsive resize
  window.addEventListener('resize', () => {
    if (viewer && viewer.context && viewer.context.renderer) {
      const width = window.innerWidth;
      const height = window.innerHeight;
      viewer.context.renderer.setSize(width, height);
      viewer.context.ifcCamera.camera.aspect = width / height;
      viewer.context.ifcCamera.camera.updateProjectionMatrix();
    }
  });
}

loadViewer();
