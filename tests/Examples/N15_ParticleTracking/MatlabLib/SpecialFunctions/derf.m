% inverse of error function in double precision */
function y=derf(x)
    n=length(x);
    y(1:n)=0;
    for i=1:n,
    y(i)=1.0-derfc(x(i));
    end;