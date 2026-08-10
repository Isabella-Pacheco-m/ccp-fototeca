/* Interacciones de la Fototeca CCP — sin dependencias externas. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    avisosDescartables();
    filtrosAutomaticos();
    limpiarBusqueda();
    visorAmpliado();
    cargaDeImagen();
    confirmaciones();
  });

  /* Cierre manual y automático de los mensajes del sistema. */
  function avisosDescartables() {
    document.querySelectorAll(".aviso__cerrar").forEach(function (boton) {
      boton.addEventListener("click", function () {
        const aviso = boton.closest(".aviso");
        aviso.style.transition = "opacity 200ms, transform 200ms";
        aviso.style.opacity = "0";
        aviso.style.transform = "translateY(-6px)";
        setTimeout(function () { aviso.remove(); }, 210);
      });
    });
  }

  /* Los selectores de filtro envían el formulario al cambiar. */
  function filtrosAutomaticos() {
    document.querySelectorAll("[data-auto-enviar]").forEach(function (control) {
      control.addEventListener("change", function () {
        const formulario = control.closest("form");
        if (!formulario) return;
        const pagina = formulario.querySelector('[name="pagina"]');
        if (pagina) pagina.value = "1";
        formulario.submit();
      });
    });
  }

  function limpiarBusqueda() {
    const boton = document.querySelector("[data-limpiar]");
    if (!boton) return;
    boton.addEventListener("click", function () {
      const campo = document.getElementById(boton.dataset.limpiar);
      if (!campo) return;
      campo.value = "";
      campo.focus();
      const formulario = campo.closest("form");
      if (formulario && boton.dataset.enviar === "1") formulario.submit();
    });
  }

  /* Ampliar la fotografía en el detalle. */
  function visorAmpliado() {
    const disparador = document.querySelector("[data-visor]");
    const lightbox = document.getElementById("lightbox");
    if (!disparador || !lightbox) return;

    const imagen = lightbox.querySelector("img");
    const abrir = function () {
      imagen.src = disparador.dataset.visor;
      lightbox.dataset.abierto = "1";
      document.body.style.overflow = "hidden";
      lightbox.querySelector(".lightbox__cerrar").focus();
    };
    const cerrar = function () {
      lightbox.dataset.abierto = "0";
      document.body.style.overflow = "";
      disparador.focus();
    };

    disparador.addEventListener("click", abrir);
    disparador.addEventListener("keydown", function (evento) {
      if (evento.key === "Enter" || evento.key === " ") {
        evento.preventDefault();
        abrir();
      }
    });
    lightbox.addEventListener("click", cerrar);
    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && lightbox.dataset.abierto === "1") cerrar();
    });
  }

  /* Zona de carga: arrastrar y soltar + previsualización antes de guardar. */
  function cargaDeImagen() {
    const zona = document.querySelector("[data-zona-carga]");
    if (!zona) return;

    const entrada = zona.querySelector('input[type="file"]');
    const previa = document.getElementById("previsualizacion");
    const nombre = zona.querySelector("[data-nombre-archivo]");

    ["dragenter", "dragover"].forEach(function (evento) {
      zona.addEventListener(evento, function (e) {
        e.preventDefault();
        zona.classList.add("zona-carga--activa");
      });
    });
    ["dragleave", "drop"].forEach(function (evento) {
      zona.addEventListener(evento, function (e) {
        e.preventDefault();
        zona.classList.remove("zona-carga--activa");
      });
    });
    zona.addEventListener("drop", function (e) {
      if (e.dataTransfer.files.length) {
        entrada.files = e.dataTransfer.files;
        entrada.dispatchEvent(new Event("change"));
      }
    });

    entrada.addEventListener("change", function () {
      const archivo = entrada.files && entrada.files[0];
      if (!archivo) return;
      if (nombre) {
        nombre.textContent = archivo.name + " · " + (archivo.size / 1024 / 1024).toFixed(1) + " MB";
      }
      if (previa) {
        const lector = new FileReader();
        lector.onload = function (e) {
          previa.hidden = false;
          previa.querySelector("img").src = e.target.result;
          const pie = previa.querySelector("[data-previa-pie]");
          if (pie) pie.textContent = "Imagen seleccionada: " + archivo.name;
        };
        lector.readAsDataURL(archivo);
      }
    });
  }

  /* Confirmación antes de acciones destructivas en un solo clic. */
  function confirmaciones() {
    document.querySelectorAll("[data-confirmar]").forEach(function (formulario) {
      formulario.addEventListener("submit", function (evento) {
        if (!window.confirm(formulario.dataset.confirmar)) evento.preventDefault();
      });
    });
  }
})();
