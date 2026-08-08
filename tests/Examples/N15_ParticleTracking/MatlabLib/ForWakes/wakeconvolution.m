function z=wakeconvolution(bunch,wake)
% convolution of unequally spaced functions
% bunch defines the parameters
nb=length(bunch(:,1));
xwi=bunch(:,1)-bunch(1,1);
wake1=interp1(wake(:,1),wake(:,2),xwi,'linear',0);
wake1(1)=wake1(1)*0.5;
ww=convolution(bunch,[xwi,wake1]);
z=[ww(1:nb,1),ww(1:nb,2)];



