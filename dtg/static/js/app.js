/* 
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################
*/

var tag_counter = 0;
var dtgstate = Object();
dtgstate.tagexcl = 1;
dtgstate.kindfilter = "flttodo";
dtgstate.timefilter = "fltall";
dtgstate.changed_tags = 0;
dtgstate.changed_contexts = 0;
dtgstate.selected_task = null;
var replaced_state = 0;
var seqid = -1;
var in_ajax = false;
var in_seqid_loading = false;
var initing = true;
var tooltip_opts = {placement: "bottom", delay: { show: 800, hide: 100 }};

var fetch_tasks;
var fetch_contexts;
var fetch_tags;
var reload_tasks = function() {
  fetch_tasks();
  $(".tooltip").remove();
}

var update_seqid_and_reload = function() {
  if (!in_ajax && !in_seqid_loading) {
    in_seqid_loading = true;
    $.ajax({
      url: create_url("seqid") + "?seqid=" + seqid,
      global: false,
      error: function () { in_seqid_loading = false; },
      success: function (data) {
        if (data.seqid != seqid && data.seqid != undefined && !in_ajax) {
          seqid = data.seqid;
          fetch_tags();
          fetch_contexts();
        }
        in_seqid_loading = false;
      }
    });
  }
  window.setTimeout(update_seqid_and_reload, 5000);
};

var update_radiobuttons = function() {
  if (dtgstate.tagexcl) {
    $("#btnexcl").click();
  } else {
    $("#btnincl").click();
  }
};

var update_timefilter = function() {
  $("#timefilter").children("#" + dtgstate.timefilter).click();
  $("#kindfilter").children("#" + dtgstate.kindfilter).click();
};

var read_url = function(url) {
  state = URI.parseQuery(url);
  dtgstate.selected_tags = Object();
  if (state.te != undefined)
    dtgstate.tagexcl = state.te;
  if (state.tf != undefined)
    dtgstate.timefilter = state.tf;
  if (state.kf != undefined)
    dtgstate.kindfilter = state.kf;
  for (field in state.stg) {
    dtgstate.selected_tags[field] = 1;
  }
  if (state.sc)
    dtgstate.selected_context = state.sc;
  update_radiobuttons();
  update_timefilter();
};

var compose_url = function() {
  var selected_tags = [];
  for (field in dtgstate.selected_tags) {
    if (dtgstate.selected_tags[field])
      selected_tags.push(field);
  }
  return "?" + $.param({stg: selected_tags, sc: dtgstate.selected_context,
                        te: dtgstate.tagexcl, tf: dtgstate.timefilter, kf: dtgstate.kindfilter});
};

var load_flashes = function() {
  $.ajax({
    url: $SCRIPT_ROOT + "_flashes?id=" + last_flash_id,
    success: function (data) {
      $.each(data.data, function(_, item) {
        if (item.id > last_flash_id && item.id != undefined)
          last_flash_id = item.id;
        $.pnotify({
          styling: 'bootstrap',
          type: 'success',
          title: notice_title,
          text: item.text,
        });
      });
    }
  });
};


var init_history = function() {
  var History = window.History;
  if (!History.enabled) {
    // History.js is disabled for this browser because it does not support HTML5
  }
  History.Adapter.bind(window, 'statechange', function() {
      var State = History.getState();
      if (!State.data.selected_tags) // sanity check
        return;
      if (replaced_state == 1) {
        replaced_state = 0;
        dtgstate.changed_tags = 0;
        dtgstate.changed_contexts = 0;
        return;
      }
      dtgstate = State.data;
      if (dtgstate.changed_tags)
        fetch_tags();
      if (dtgstate.changed_contexts)
        fetch_contexts();
      update_radiobuttons();
      dtgstate.changed_tags = 0;
      dtgstate.changed_contexts = 0;
  });
};

var push_state = function() {
  History.pushState(dtgstate, document.title, compose_url());
};

var create_url = function(suffix) {
  return window.location.pathname + ((window.location.pathname.substring(window.location.pathname.length - 1) == "/") ? "" : "/") + suffix;
};


var create_fetcher = function(elemname, tmplname, url, idprefix, propname, selpropname, changedattr, reloader, filler, multiprop, is_task_list) {
  var func = function() {
    var elem = $(elemname);
    var tmplelem = $(tmplname);
    var selfreloader = func;
    params = "";
    type = "GET";
    if (is_task_list) {
      sels = [];
      for (field in dtgstate.selected_tags) {
        if (dtgstate.selected_tags[field])
          sels.push(field);
      }
      params = {selected_context: dtgstate.selected_context, selected_tags: sels, tagexcl: dtgstate.tagexcl, timefilter: dtgstate.timefilter,
                kindfilter: dtgstate.kindfilter};
      type = "POST";
    }
    $.ajax({
      type: type,
      url: create_url(url),
      data: params,
      success: function (data) {
        seqid = data.seqid;
        data = data.data;
        dtgstate[propname] = data;
        if (multiprop) {
          var need_init = 1;
          for (_ in dtgstate[selpropname]) {
            need_init = 0;
            break;
          }
          if (need_init) {
            $.each(data, function(_, value) {
              dtgstate[selpropname][value.id] = 1;
            });
          }
        } else {
          if (data && dtgstate[selpropname] == undefined && !is_task_list) {
            dtgstate[selpropname] = data[0].id;
          }
        }
        elem.empty();
        $.each(data, function(index, value) {
          var item = tmplelem.clone();
          if (!multiprop) {
            item.addClass("ui-state-default");
            if (data.length == 1)
              item.find(".deletecontext").remove();
          } else {
            item.addClass(dtgstate[selpropname][value.id] ? "ui-state-active" : "ui-state-default");
            if (is_task_list) {
              if (dtgstate[selpropname][value.id]) {
                item.find(".taskbody").show();
              } else {
                item.find(".taskbody").hide();
              }
            }
          }
          item.attr("id", idprefix + value.id);
          item.attr("internalid", value.id);
          filler(item, value);
          item.find("*[title]").tooltip(tooltip_opts);
          if (!multiprop) {
            if (!is_task_list) {
              item.droppable({
                hoverClass: "ui-state-hover",
                tolerance: "pointer",
                over: function(event, ui) {
                  if (ui.draggable.hasClass("task") && !item.hasClass("movetarget")) {
                    item.addClass("movetarget")
                  }
                  $("#tasklist").data("docancel", 1);
                },
                out: function(event, ui) {
                  if (ui.draggable.hasClass("task")) {
                    if (item.hasClass("movetarget")) {
                      item.removeClass("movetarget")
                    }
                  }
                },
                drop: function( event, ui ) {
                  if (ui.draggable.hasClass("task")) {
                    if (item.hasClass("movetarget")) {
                      item.removeClass("movetarget")
                    }
                    $.ajax({
                      type: "POST",
                      url: create_url(url),
                      data: {action: "move_task", id: item.attr("internalid"), task_id: ui.draggable.attr("internalid")},
                      success: function (data) {
                        if (!data.result == "OK")
                          alert("Moving failed");
                        $("#tasklist").data("docancel", 0);
                        selfreloader();
                        push_state();
                      }
                    });
                  }
                }
              });
            }
            item.click(function(e) {
              if (value.id != dtgstate[selpropname]) {
                elem.children("li").each(function(i) {
                  $(this).removeClass("ui-state-active");
                  $(this).removeClass("ui-state-default");
                  $(this).addClass("ui-state-default");
                  $(this).find(".taskbody").fadeOut();
                });
                item.addClass("ui-state-active");
                item.removeClass("ui-state-default");
                dtgstate[selpropname] = value.id;
              } else {
                item.addClass("ui-state-active");
                item.removeClass("ui-state-default");
              }
              if (is_task_list) {
                if (dtgstate[selpropname] == value.id) {
                  item.find(".taskbody").fadeIn();
                } else {
                  item.find(".taskbody").fadeOut();
                }
              } else {
                reloader();
                push_state();
              }
            });
          } else {
            item.click(function(e) {
              dtgstate[changedattr] = 1;
              if (dtgstate[selpropname][value.id]) {
                item.removeClass("ui-state-active");
                item.addClass("ui-state-default");
                dtgstate[selpropname][value.id] = 0;
              } else {
                item.addClass("ui-state-active");
                item.removeClass("ui-state-default");
                dtgstate[selpropname][value.id] = 1;
              }
              if (!is_task_list)
                reloader();
              push_state();
            });
          }
          elem.append(item);
        });
        elem.sortable({
          distance: 5,
          forcePlaceholderSize: true,
          placeholder: "ui-state-highlight",
          start: function(event, ui) {
            if ($(event.originalEvent.target).hasClass("taskbody"))
              event.preventDefault();

            $(ui.placeholder).css({"height": ui.item.height()});
            if (multiprop && !is_task_list) {
              $(".task").addClass("ui-state-highlight");
            } else if (is_task_list) {
              $(".context").addClass("ui-state-highlight");
            }
          },
          stop: function(event, ui) {
            if (multiprop && !is_task_list) {
              $(".task").removeClass("ui-state-highlight");
            } else if (is_task_list) {
              $(".context").removeClass("ui-state-highlight");
            }
            if (ui.item && !elem.data("docancel")) {
              var previous_item = ui.item.prev();
              var previous_item_id = -1;
              if (previous_item.length != 0)
                previous_item_id = previous_item.attr("internalid");
              $.ajax({
                type: "POST",
                url: create_url(url),
                data: {action: "move", id: ui.item.attr("internalid"), previous_id: previous_item_id},
                success: function (data) {
                  if (!data.result == "OK")
                    alert("Moving failed");
                  dtgstate[changedattr] = 1;
                  if (is_task_list)
                    selfreloader();
                  else if (multiprop) // tag order can also change in the tasks display
                    reload_tasks();
                  push_state();
                }
              });
            }
          }
        });
        if (!multiprop && !is_task_list) {
          var child;
          child = elem.children("#" + idprefix + dtgstate[selpropname]).first();
          child.addClass("ui-state-active");
          child.removeClass("ui-state-default");
          window.setTimeout(reloader, 0);
          if (initing) {
            dtgstate.changed_contexts = 1;
            replaced_state = 1;
            History.replaceState(dtgstate, document.title);
            initing = false;
          }
        }
      }
    });
  };
  return func;
};

var make_edit_callable = function(item, func) {
  return function(e) {
    func(item);
    e.stopPropagation();
  };
};

var create_editor = function(url, reloader, selpropname) {
  return function(item, create_or_id) {
    var internalid;
    if (create_or_id != undefined) {
      internalid = create_or_id;
    } else {
      internalid = item.attr("internalid");
    }
    $.ajax({
      type: "POST",
      url: create_url(url),
      data: {action: "editinitial", id: internalid},
      success: function (data) {
        var dialog = $(".editdialog");
        var saver = function() {
          var datastr = $("#editform").serialize();
          datastr += "&action=edit&id=" + internalid;
          $.ajax({
            type: "POST",
            url: create_url(url),
            data: datastr,
            success: function (data) {
              if (data.status === "AGAIN") {
                dialog.find("#editdialogtitle").text(data.title);
                dialog.find("#editdialogbody").html(data.body).find("*[title]").tooltip(tooltip_opts);
              } else {
                dialog.find(".cancelbutton").click();
                if (create_or_id != undefined && create_or_id != -1 && selpropname != undefined)
                  dtgstate[selpropname][data.id] = 1;
                reloader();
                load_flashes();
              }
            }
          });
        };
        dialog.find("#editdialogtitle").text(data.title);
        dialog.find("#editdialogbody").html(data.body).find("*[title]").tooltip(tooltip_opts);
        dialog.find(".btn-primary").off("click").click(function () {
          saver();
          return false;
        });
        dialog.find("#masterjump").click(function() {
          dialog.find(".cancelbutton").click();
          window.setTimeout(function() { edit_task(0, item.attr("master-task-id")); }, 1500); // XXX ugly
        });
        dialog.modal();
      }
    });
  };
};

var create_deleter = function(url, reloader) {
  return function(item) {
    var internalid = item.attr("internalid");

    $(".deletedialog .deletebutton").off("click").click(function() {
      $.ajax({
        type: "POST",
        url: create_url(url),
        data: {action: "delete", id: internalid},
        success: function (data) {
          reloader();
          $(".deletedialog .cancelbutton").click();
          load_flashes();
        }
      });
    });
    $(".deletedialog").modal();
    return false;
  };
};

var edit_context = create_editor("contexts", function() { fetch_contexts(); });
var edit_tag = create_editor("tags", function() { fetch_tags(); }, "selected_tags");
var edit_task = create_editor("tasks", function() { fetch_tasks(); });
var delete_context = create_deleter("contexts", function() { dtgstate.selected_context = undefined; fetch_contexts(); });
var delete_tag = create_deleter("tags", function() { dtgstate.selected_tags = Object(); fetch_tags(); });
var delete_task = create_deleter("tasks", function() { dtgstate.selected_task = null; fetch_tasks(); });
var fill_context = function(item, data) {
  item.find(".contextname").text(data.name);
  item.find(".editcontext").click(make_edit_callable(item, edit_context));
  item.find(".deletecontext").click(make_edit_callable(item, delete_context));
}
var fill_tag = function(item, data) {
  item.find(".tagname").text(data.name);
  item.find(".edittag").click(make_edit_callable(item, edit_tag));
  item.find(".deletetag").click(make_edit_callable(item, delete_tag));
}
var fill_task = function(item, data) {
  item.attr("master-task-id", data.master_task_id);
  var tagtmpl = $("#tagtmpl");
  item.find(".tasksummary").text(data.name);
  item.find(".taskdescription").html(data.body);
  item.find(".taskbody").hover(function() {
    $("#tasklist").sortable("disable");
  }, function() {
    $("#tasklist").sortable("enable");
  });
  if (data.completion_time)
    item.find(".taskcompletiontime").text(data.completion_time);
  else
    item.find(".taskcompletion").remove();

  if (!data.is_recurring)
    item.find(".recurringmarker").remove();
  if (data.due_marker != null) {
    item.find(".dueindays").addClass(data.due_marker[2]).text(data.due_marker[1]);
  } else {
    item.find(".dueindays").remove();
  }
  if (data.completed) {
    item.find(".incompletetxt").show();
    item.find(".dueindays").remove();
  } else {
    item.find(".completetxt").show();
  }
  var tasktags = item.find(".tasktags");
  tasktags.empty();
  $.each(data.tags, function(_, tagitem) {
    var clone = tagtmpl.clone().attr("id", "tag-" + tag_counter++).attr("internalid", tagitem.id);
    clone.find(".tagname").text(tagitem.name);
    clone.draggable({
      revert: true,
      distance: 4,
    });
    clone.data("container", item);
    clone.mouseup(function() {
      if (clone.data("shouldberemoved") != undefined && clone.data("shouldberemoved") != null) {
        $.ajax({
          type: "POST",
          url: create_url("tasks"),
          data: {action: "remove_tag", id: data.id, tag_id: tagitem.id},
          success: function (data) {
            clone.remove();
          }
        });
      }
    });
    tasktags.append(clone);
  });
  item.droppable({
    drop: function(e, ui) {
      if (ui.draggable.hasClass("taglistitem")) {
        if (item.hasClass("movetarget")) {
          item.removeClass("movetarget")
        }
        $.ajax({
          type: "POST",
          url: create_url("tasks"),
          data: {action: "add_tag", id: data.id, tag_id: ui.draggable.attr("internalid")},
          success: function (data) {
            fetch_tasks();
          }
        });
      }
    },
    over: function(e, ui) {
      if (ui.draggable.hasClass("taglistitem") && !item.hasClass("movetarget")) {
        item.addClass("movetarget")
      }
      if (ui.draggable.hasClass("taglabel") && ui.draggable.data("shouldberemoved") == item) {
        ui.draggable.data("shouldberemoved", null);
      }
    },
    out: function(e, ui) {
      if (ui.draggable.hasClass("taglistitem") && item.hasClass("movetarget")) {
        item.removeClass("movetarget")
      }
      if (ui.draggable.hasClass("taglabel") && ui.draggable.data("container") == item) {
        ui.draggable.data("shouldberemoved", item);
      }
    }
  });
  item.find(".edittask").click(make_edit_callable(item, edit_task));
  item.find(".deletetask").click(make_edit_callable(item, delete_task));
  item.find(".completetask").click(function(e) {
    $.ajax({
      type: "POST",
      url: create_url("tasks"),
      data: {action: "togglecomplete", id: data.id},
      success: function (data) {
        reload_tasks();
        load_flashes();
      }
    });
    e.stopPropagation();
  });
  item.find(".postponetask").click(function(e) {
    $.ajax({
      type: "POST",
      url: create_url("tasks"),
      data: {action: "postpone", id: data.id},
      success: function (data) {
        reload_tasks();
        load_flashes();
      }
    });
    e.stopPropagation();
  });
}
fetch_contexts = create_fetcher("#contextlist", "#contextrowtmpl", "contexts", "contextlist-", "contexts", "selected_context", "changed_contexts", reload_tasks, fill_context);
fetch_tags = create_fetcher("#taglist", "#tagrowtmpl", "tags", "tagslist-", "tags", "selected_tags", "changed_tags", reload_tasks, fill_tag, 1);
fetch_tasks = create_fetcher("#tasklist", "#taskrowtmpl", "tasks", "tasklist-", "tasks", "selected_task", "meow", reload_tasks, fill_task, 0, 1);

var setup_preferences_button = function() {
  var url = $SCRIPT_ROOT + "/preferences";
  $("#preferences").click(function() {
    $.ajax({
      type: "POST",
      url: url,
      success: function (data) {
        var dialog = $(".editdialog");
        var saver = function() {
          var datastr = $("#editform").serialize();
          $.ajax({
            type: "POST",
            url: url,
            data: datastr,
            success: function (data) {
              if (data.status === "AGAIN") {
                dialog.find("#editdialogtitle").text(data.title);
                dialog.find("#editdialogbody").html(data.body).find("*[title]").tooltip(tooltip_opts);
              } else {
                dialog.find(".cancelbutton").click();
                if (data.status === "LOCALECHANGE") {
                  window.location.reload();
                } else {
                  load_flashes();
                }
              }
            }
          });
        };
        dialog.find("#editdialogtitle").text(data.title);
        dialog.find("#editdialogbody").html(data.body).find("*[title]").tooltip(tooltip_opts);
        dialog.find(".btn-primary").off("click").click(function () {
          saver();
          return false;
        });
        dialog.modal();
      }
    });
    return false;
  });
};

var ajax_setup = function() {
  $.ajaxSetup({
    error: function (jqXHR, status, error) {
      $("#errmsg").text(error);
      $(".errbox").modal();       
    },
    ajaxStart: function() {
      in_ajax = true;
    },
    ajaxStop: function() {
      in_ajax = false;
    }
  });
  $('#ajaxloading').ajaxStart(function() {
    $(this).css("visibility", "visible");
  }).ajaxComplete(function() {
    $(this).css("visibility", "hidden");
  });
};

var init_mainview = function() {
  ajax_setup();
  init_history();
  read_url(document.location.search);
  fetch_tags();
  fetch_contexts();
  $("#newtaskform").submit(function() {
    if (this.newtasksummary.value) {
      $.ajax({
        type: "POST",
        url: create_url("tasks"),
        data: {action: "create", summary: this.newtasksummary.value, selected_context: dtgstate.selected_context},
        success: function (data) {
          $("#newtasksummary").val("");
          load_flashes();
          reload_tasks();
        }
      });
    }
    return false;
  });
  $("#newtasksummary").typeahead({
    source: function(typeahead, query) {
      $.ajax({
        type: "POST",
        url: create_url("tasks"),
        data: {action: "typeahead", summary: query},
        success: function (data) {
          typeahead.process(data.list);
        }
      });
      return false;
    }
  });
  $("#btnexcl").click(function() {
    if (dtgstate.tagexcl != 1) {
      dtgstate.tagexcl = 1;
      reload_tasks();
      push_state();
    }
  });
  $("#btnincl").click(function() {
    if (dtgstate.tagexcl != 0) {
      dtgstate.tagexcl = 0;
      reload_tasks();
      push_state();
    }
  });
  var filtersetup = function(handle, propname) {
    $(handle).children().click(function() {
      window.setTimeout(function() {
        var newstate = $(handle).children(".active").attr("id");
        if (dtgstate[propname] != newstate) {
          dtgstate[propname] = newstate;
          reload_tasks();
          push_state();
        }
      });
    });
  };
  filtersetup("#timefilter", "timefilter");
  filtersetup("#kindfilter", "kindfilter");

  $(".addcontext").click(function() {
    edit_context(0, -1);
  });
  $(".addtag").click(function() {
    edit_tag(0, -1);
  });
  setup_preferences_button();
  $("#workspacedelete").click(function() {
    $(".deletedialog .deletebutton").off("click").click(function() {
      $.ajax({
        type: "POST",
        url: create_url("delete"),
        success: function (data) {
          window.location.href = $SCRIPT_ROOT + "/";
        }
      });
    });
    $(".deletedialog").modal();
    return false;
  });
  $("#workspacerename").click(function() {
    var answer = prompt(workspace_rename_prompt, workspace_name);
    if (!answer)
      return false;
    $.ajax({
      type: "POST",
      data: "name=" + encodeURIComponent(answer),
      url: create_url("rename"),
      success: function (data) {
        window.location.href = $SCRIPT_ROOT + "/" + encodeURIComponent(data.name);
      }
    });
    return false;
  });
  window.setTimeout(update_seqid_and_reload, 5000);
  $(".row-fluid").find("*[title]").tooltip(tooltip_opts);
};

var init_workspace_view = function() {
  ajax_setup();
  setup_preferences_button();
  $("*").tooltip(tooltip_opts);
  $("#newworkspaceform").submit(function() {
    $.ajax({
      type: "POST",
      url: create_url("_workspaces"),
      data: {action: "create", name: this.newworkspacename.value},
      success: function (data) {
        window.location.reload();
      }
    });
    return false;
  });
};

