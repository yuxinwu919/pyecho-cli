% inverse of error function in double precision */
function x=dierf(y)
    n=length(y);
    x(1:n)=0;
    for i=1:n,
    x(i)=dierfc(1-y(i));
    end;