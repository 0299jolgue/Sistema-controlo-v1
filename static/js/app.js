document.querySelectorAll('[data-confirm]').forEach(e=>e.addEventListener('click',x=>{if(!confirm(e.dataset.confirm))x.preventDefault()}));
