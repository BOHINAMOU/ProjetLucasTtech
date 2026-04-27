document.addEventListener("DOMContentLoaded", function () {
    console.log("Admin personnalisé 🚀");

    // Animation simple
    document.querySelectorAll('.module').forEach(el => {
        el.style.transition = "0.3s";
        el.addEventListener('mouseenter', () => {
            el.style.transform = "scale(1.02)";
        });
        el.addEventListener('mouseleave', () => {
            el.style.transform = "scale(1)";
        });
    });
});
document.addEventListener("DOMContentLoaded", function () {

    // Ajouter une animation sur les apps
    document.querySelectorAll('.app-list .model').forEach(el => {
        el.style.cursor = "pointer";

        el.addEventListener('click', () => {
            el.style.background = "#6366f1";
        });
    });

});