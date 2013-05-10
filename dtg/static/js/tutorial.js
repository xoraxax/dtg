var _ = function(x) { return x; };

var TUTORIAL = {
    0: null, /* tutorial finished/skipped */
    /* the next tutorial task is: */
    1: [_('Welcome to <em>Done Tasks Gone</em>! Using this tutorial, you will learn most of the nifty features of DTG. Note that even outside the tutorial, you can always hover your mouse over a particular element to see a short description. <br><a href="#" class="btn" id="continuetutorial">Start the tutorial!</a>'), 101, ".brand", "bottom", ["click", "#continuetutorial"]],
    101: [_("Create a new task by entering its summary and pressing Return or the <em>Create</em> button."), 2, "#newtasksummary", "bottom", ["click", "#createtaskbtn"]],
		2: [_("Create a new context by clicking the <em>Add</em> button."), 3, ".addcontext", "right", ["contexts_loaded"]],
		3: [_("Move your new task by dragging and dropping it onto your newly created context."), 4, "ul#tasklist li:first", "bottom", ["move_task"]],
		4: [_("Select your newly created context by clicking it."), 5, "ul#contextlist li:last", "right", ["clickpot"]],
		5: [_("Create a tag by clicking the <em>Add</em> button."), 6, ".addtag", "right", ["click_added_tag"]],
		6: [_("Assign the new tag by dragging it and dropping it on the task"), 7, "ul#taglist li:last", "bottom", ["assign_tag"]],
		7: [_("Deselect your tag to see how tasks with tags can be excluded."), 8, "ul#taglist li:last", "bottom", ["clickpot"]],
		8: [_("Select your tag again."), 9, "ul#taglist li:last", "bottom", ["tasks_loaded"]],
		9: [_("Postpone your task - this is useful if you do not want to complete it on the planned due date."), 10, "ul#tasklist > li:last .postponetask", "bottom", ["tasks_loaded"]],
		10: [_("You are done with your task, click <em>Complete</em>."), 11, "ul#tasklist > li:last .completetask", "bottom", ["clickpot"]],
		11: [_("You want to see the completed tasks, click <em>Completed</em>."), 12, "#fltdone", "bottom", ["clickpot"]],
		12: [_("You want to see the active tasks again, click <em>To do</em>."), 13, "#flttodo", "bottom", ["clickpot"]],
    13: [_("Create a new task again."), 14, "#newtasksummary", "bottom", ["click", "#createtaskbtn"]],
		14: [_("Now you want to edit the details of the task, click <em>Edit</em>."), 141, "ul#tasklist > li:last .edittask", "bottom", ["editor_loaded"]],
		141: [_("Your task should be hidden until a certain day has begun. Set the <em>visible from</em> date to the future."), 1410, "#visible_from", "top", ["clickpot"]],
		1410: [_("Your task should also be due on some date. Set the <em>due date</em> date to the future and past the visible from date."), 142, "#due", "top", ["clickpot"]],
    142: [_("You want to store details of the task, edit the <em>description</em>. You may use Markdown markup (look it up if you do not know it!)."), 143, "#description", "top", ["clickpot"]],
		143: [_("Your task should repeat itself. Think about an interval like 'every 1 day<b>s</b>' and enter it."), 144, "#recur_procedure", "right", ["clickpot"]],
    144: [_("Save your changes."), 15, "#editform .btn-primary", "top", ["clickpot"]],
		15: [_("Now the original task was converted to a recurrence template and a slave task was created. Switch to <em>recurrence templates</em> to view your master task."), 16, "#flttmpl", "bottom", ["tasks_loaded"]],
		16: [_("In order to view your assigned description, click the task."), 17, "ul#tasklist li.task:first", "bottom", ["clickpot"]],
		17: [_('Switch to <em>To Do</em> again to be able to work with new tasks.'), 180, "#flttodo", "bottom", ["clickpot"]],
    180: [_("Create a new task again."), 181, "#newtasksummary", "bottom", ["click", "#createtaskbtn"]],
    181: [_("Create another task."), 19, "#newtasksummary", "bottom", ["tasks_loaded"]],
		19: [_("Reorder your tasks by using drag and drop. You can also reorder tags and contexts."), 20, "ul#tasklist > li:last", "bottom", ["reorder_tasks"]],
    20: [_("Thank you for completing this tutorial! We hope that you can now enjoy DTG to a better extent."), 0, ".brand", "bottom", [null]],
};

var FEATURES = {
  0: [_("DTG now supports a tutorial that will present the basic features to the user!"), 1],
  1: [_("DTG now supports an offline mode. Simply activate it using the top menu, go offline on your mobile phone etc., perform changes, and sync these later on using the top menu."), 2],
  2: null,
};

var run_featureinfo_and_tutorial = function(fidx, tidx) {
  var step = FEATURES[fidx];
  if (step == null)
    run_tutorial(tidx);
  else {
    var txt = step[0];
    var nextstep = step[1];
    var popovertarget = $(".brand");
    $.ajax({
      url: $SCRIPT_ROOT + "/_translate",
      data: {txt: txt},
      type: "POST",
      success: function (data) {
        txt = feature_title + data.txt + feature_trailer;
        popovertarget.popover({title: '', container: "body", placement: "bottom", content: txt, html: true, trigger: "manual"});
        popovertarget.popover("show");
        var next_func;
        $("#nextfeature").click(function () {
          next_func();
        });
        next_func = function () {
          popovertarget.popover("destroy");
          $(".popover").remove();
          $.ajax({
            url: $SCRIPT_ROOT + "/_update_idx",
            data: {idx: nextstep, kind: "feature"},
            type: "POST",
            success: function (data) {
              run_featureinfo_and_tutorial(nextstep, tidx);
            },
          });
        };
      }
    });
  }
};

var run_tutorial = function(idx) {
  if (idx == 0) {
    return;
  }
  var step = TUTORIAL[idx];
  var txt = step[0];
  var nextstep = step[1];
  var selpopover = step[2];
  var poplacement = step[3];
  var opdesc = step[4];
  var op = opdesc[0];
  var popovertarget = $(selpopover);
  if (popovertarget.length == 0)
    return window.setTimeout(function() { run_tutorial(idx); }, 500);

  $.ajax({
    url: $SCRIPT_ROOT + "/_translate",
    data: {txt: txt},
    type: "POST",
    success: function (data) {
      txt = tutorial_title + data.txt + tutorial_trailer;
      popovertarget.popover({title: '', container: "body", placement: poplacement, content: txt, html: true, trigger: "manual"});
      popovertarget.popover("show");
      $(".popover").zIndex(2000);
      var next_func;
      $("#stoptutorial").click(function () {
        nextstep = 0;
        reset_tutorial_hooks();
        next_func();
      });
      $("#skiptutorialstep").click(function () {
        reset_tutorial_hooks();
        next_func();
      });
      next_func = function () {
        if (op == "click")
          $(opdesc[1]).off("click", next_func);
        else if (op == "clickpot")
          popovertarget.off("click", next_func);
        popovertarget.popover("destroy");
        $(".popover").remove();
        $.ajax({
          url: $SCRIPT_ROOT + "/_update_idx",
          data: {idx: nextstep, kind: "tutorial"},
          type: "POST",
          success: function (data) {
            window.setTimeout(function() { run_tutorial(nextstep); }, 100);
          },
        });
      };
      if (op == null)
        ;
      else if (op == "clickpot")
        popovertarget.click(next_func);
      else if (op == "click")
        $(opdesc[1]).click(next_func);
      else
        tutorial_hooks[op] = next_func;
    }
  });
};

