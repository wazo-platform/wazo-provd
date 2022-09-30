# -*- coding: utf-8 -*-
# Copyright (C) 2011-2014 Avencall
# SPDX-License-Identifier: GPL-3.0-or-later

OIP_WAITING = 'waiting'
OIP_PROGRESS = 'progress'
OIP_SUCCESS = 'success'
OIP_FAIL = 'fail'


class OperationInProgress:
    """Base class for operations in progress.
    
    An operation in progress is a monitor over an underlying operation. It's
    used to expose the status of an underlying operation in a standard way.
    
    Operation in progress instances have the following attributes:
      label -- the label identifying the underlying operation, or None
      state -- the state of the operation; one of waiting, progress, success
       or fail
      current -- a non-negative integer representing the current 'step' of
        the operation, or None
      end -- a positive integer representing the last 'step' of the operation,
        or None
      sub_oips -- a list of operation in progress instances representing sub
        operations of the underlying operation
    
    Here's some general rules to follow:
    - an operation state goes from waiting to progress to one of success or
      fail. From the exterior, the operation state MUST always follow this
      sequence.
    - an operation that has sub operations is completed (i.e. in state success
      or fail) only after all of its sub operations are completed.
    - you can add more sub operations to an operation but you can't remove
      already added sub operations.
    
    """
    def __init__(self, label=None, state=OIP_WAITING, current=None, end=None, sub_oips=[]):
        self.label = label
        self.state = state
        self.current = current
        self.end = end
        self.sub_oips = list(sub_oips)


def format_oip(oip):
    """Format an operation in progress to a string.
    
    The format is '[label|]state[;current[/end]](\(sub_oips\))*'.
    
    Here's some examples:
      progress
      download|progress
      download|progress;10
      download|progress;10/100
      download|progress(file_1|progress;20/100)(file_2|waiting;0/50)
      download|progress;20/150(file_1|progress)(file_2|waiting)
      op|progress(op1|progress(op11|progress)(op12|waiting))(op2|progress)
      
    """
    s = ''
    if oip.label is not None:
        s += '%s|' % oip.label
    s += oip.state
    if oip.current is not None:
        s += ';%s' % oip.current
        if oip.end:
            s += '/%s' % oip.end
    for sub_oip in oip.sub_oips:
        s += '(%s)' % format_oip(sub_oip)
    return s


def operation_in_progres_from_deferred(deferred, label=None):
    """Return an operation in progress where the underlying operation is
    determined by a deferred.
    
    """
    def callback(res):
        oip.state = OIP_SUCCESS
        return res
    def errback(err):
        oip.state = OIP_FAIL
        return err
    oip = OperationInProgress(label, OIP_PROGRESS)
    deferred.addCallbacks(callback, errback)
    return oip
