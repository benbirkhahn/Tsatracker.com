/* Make wide editorial tables usable without horizontally scrolling the page. */
(function(){
  document.querySelectorAll('.page-prose table, .guide-body table').forEach(function(table){
    var wrapper=document.createElement('div');
    wrapper.className='flow-table-scroll';wrapper.tabIndex=0;
    wrapper.setAttribute('role','region');wrapper.setAttribute('aria-label','Scrollable comparison table');
    table.parentNode.insertBefore(wrapper,table);wrapper.appendChild(table);
  });
})();
